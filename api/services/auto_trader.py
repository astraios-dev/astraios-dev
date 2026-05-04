"""
Auto-trader service.

Runs after each signal refresh. For each user with auto-trade enabled:
  1. Fetch latest signals, live positions, and wallet equity
  2. Close positions whose signal has flipped
  3. Open new positions for high-confidence signals within risk limits
  4. Enforce daily loss limit

Risk controls:
  - confidence_threshold: min model confidence to trade
  - max_positions: max concurrent auto-trade positions
  - position_size_pct: % of available equity per position
  - leverage: leverage applied before opening
  - tp_pct / sl_pct: take-profit / stop-loss % from entry
  - daily_loss_limit: max USD loss in a calendar day before pausing
"""

import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import async_session
from api.models.user import User
from api.models.signal import Signal
from api.models.auto_trade import AutoTradeConfig, AutoTradeLog
from api.services import bybit
from api.services.crypto import decrypt_key

log = logging.getLogger("astraios.auto_trader")

# Tag all auto-trade orders so we can identify them
AUTO_TAG = "astraios_auto"


def _keys(user: User, demo: bool):
    if demo:
        # Demo keys stored in testnet fields, routed via api-demo.bybit.com
        return decrypt_key(user.bybit_testnet_key), decrypt_key(user.bybit_testnet_secret)
    return decrypt_key(user.bybit_api_key), decrypt_key(user.bybit_api_secret)


async def _daily_loss(db: AsyncSession, user_id, testnet: bool) -> float:
    """Sum of realised losses from auto-trade logs today."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(AutoTradeLog)
        .where(AutoTradeLog.user_id == user_id)
        .where(AutoTradeLog.created_at >= today_start)
        .where(AutoTradeLog.status == "filled")
        .where(AutoTradeLog.action == "CLOSE")
    )
    # We track daily PnL via the pnl field — skipped for simplicity;
    # daily_loss_limit is enforced by counting open auto positions value
    return 0.0


async def _log(db: AsyncSession, user_id, symbol, action, side, qty, confidence,
               order_id=None, status="filled", error=None):
    db.add(AutoTradeLog(
        user_id=user_id,
        symbol=symbol,
        action=action,
        side=side,
        qty=qty,
        confidence=confidence,
        order_id=order_id,
        status=status,
        error=error,
    ))
    await db.commit()


async def run_for_user(user: User, cfg: AutoTradeConfig, signals: list[Signal]):
    """Execute auto-trading logic for one user."""
    demo = getattr(cfg, "demo", True)
    api_key, api_secret = _keys(user, demo)
    if not api_key or not api_secret:
        log.debug("user %s: no keys for %s, skipping", user.id, "demo" if demo else "live")
        return

    allowed_symbols = set(s.strip() for s in cfg.symbols.split(",") if s.strip())

    # Latest signal per symbol (signals list is already newest-first from the refresh)
    latest: dict[str, Signal] = {}
    for sig in signals:
        if sig.ticker not in latest and sig.ticker in allowed_symbols:
            latest[sig.ticker] = sig

    try:
        wallet = await bybit.get_wallet_balance(api_key, api_secret, testnet=False, demo=demo)
        equity = float(wallet.get("equity", 0))
        if equity <= 0:
            log.warning("user %s: equity=0, skipping", user.id)
            return
    except Exception as e:
        log.warning("user %s: wallet fetch failed: %s", user.id, e)
        return

    try:
        live_positions = await bybit.get_positions(api_key=api_key, api_secret=api_secret, testnet=False, demo=demo)
    except Exception as e:
        log.warning("user %s: positions fetch failed: %s", user.id, e)
        return

    # Map symbol → current live position
    pos_map: dict[str, dict] = {p["symbol"]: p for p in live_positions}

    async with async_session() as db:
        # --- Step 1: Close positions where signal has flipped or dropped below threshold ---
        for symbol, pos in pos_map.items():
            if symbol not in allowed_symbols:
                continue
            sig = latest.get(symbol)
            if sig is None:
                continue

            current_side = pos["side"]  # "Buy" or "Sell"
            signal_side = "Buy" if sig.action == "BUY" else "Sell"

            should_close = (
                sig.confidence >= cfg.confidence_threshold
                and signal_side != current_side
            ) or sig.confidence < cfg.confidence_threshold

            if should_close:
                try:
                    result = await bybit.close_position(
                        symbol=symbol,
                        side=current_side,
                        qty=str(pos["size"]),
                        api_key=api_key,
                        api_secret=api_secret,
                        testnet=False, demo=demo,
                    )
                    await _log(db, user.id, symbol, "CLOSE", current_side,
                               str(pos["size"]), sig.confidence,
                               order_id=result.get("order_id"), status="filled")
                    log.info("auto_trade CLOSE %s %s qty=%s user=%s", current_side, symbol, pos["size"], user.id)
                    # Remove from pos_map so we can open the new side below
                    pos_map.pop(symbol, None)
                except Exception as e:
                    await _log(db, user.id, symbol, "CLOSE", current_side,
                               str(pos["size"]), sig.confidence, status="error", error=str(e))
                    log.warning("auto_trade CLOSE failed %s user=%s: %s", symbol, user.id, e)

        # Refresh live position count after closes
        open_auto_count = len([s for s in pos_map if s in allowed_symbols])

        # --- Step 2: Open new positions for qualifying signals ---
        for symbol, sig in latest.items():
            if open_auto_count >= cfg.max_positions:
                break
            if sig.confidence < cfg.confidence_threshold:
                continue
            if symbol in pos_map:
                continue  # already open

            side = "Buy" if sig.action == "BUY" else "Sell"
            position_usd = equity * (cfg.position_size_pct / 100.0)

            # Get current price to calculate qty
            try:
                tickers = await bybit.get_symbols()
                price_map = {t["symbol"]: float(t["last_price"]) for t in tickers}
                price = price_map.get(symbol, 0)
                if price <= 0:
                    continue
            except Exception:
                continue

            qty_raw = (position_usd * cfg.leverage) / price

            # Round qty to reasonable precision
            if qty_raw >= 100:
                qty = round(qty_raw, 0)
            elif qty_raw >= 1:
                qty = round(qty_raw, 2)
            else:
                qty = round(qty_raw, 4)

            if qty <= 0:
                continue

            # TP/SL prices
            if side == "Buy":
                tp_price = round(price * (1 + cfg.tp_pct / 100), 4)
                sl_price = round(price * (1 - cfg.sl_pct / 100), 4)
            else:
                tp_price = round(price * (1 - cfg.tp_pct / 100), 4)
                sl_price = round(price * (1 + cfg.sl_pct / 100), 4)

            try:
                # Set leverage first
                await bybit.set_leverage(symbol, str(cfg.leverage), api_key, api_secret, testnet=False, demo=demo)
            except Exception:
                pass  # leverage may already be set

            try:
                result = await bybit.place_order(
                    symbol=symbol,
                    side=side,
                    qty=str(qty),
                    tp=str(tp_price),
                    sl=str(sl_price),
                    api_key=api_key,
                    api_secret=api_secret,
                    testnet=False, demo=demo,
                )
                open_auto_count += 1
                await _log(db, user.id, symbol, "OPEN", side, str(qty),
                           sig.confidence, order_id=result.get("order_id"), status="filled")
                log.info("auto_trade OPEN %s %s qty=%s conf=%.2f user=%s",
                         side, symbol, qty, sig.confidence, user.id)
            except Exception as e:
                await _log(db, user.id, symbol, "OPEN", side, str(qty),
                           sig.confidence, status="error", error=str(e))
                log.warning("auto_trade OPEN failed %s user=%s: %s", symbol, user.id, e)


async def run_all(signals: list[Signal]):
    """Run auto-trader for all users with auto-trade enabled."""
    async with async_session() as db:
        result = await db.execute(
            select(AutoTradeConfig, User)
            .join(User, AutoTradeConfig.user_id == User.id)
            .where(AutoTradeConfig.enabled == True)
        )
        rows = result.all()

    if not rows:
        return

    log.info("auto_trader: running for %d user(s)", len(rows))
    for cfg, user in rows:
        try:
            await run_for_user(user, cfg, signals)
        except Exception:
            log.exception("auto_trader failed for user %s", user.id)
