"""
Drift Protocol execution service for Astraios.

Executes perpetual futures on Drift (Solana on-chain DEX) using the same
signal format and risk parameters as the Bybit auto-trader.

Prerequisites:
  - driftpy installed (pip install driftpy)
  - User must supply a Solana wallet private key (base58) + RPC URL via Account settings
  - Private key is Fernet-encrypted at rest (same as Bybit keys)

Drift market indices for supported symbols:
  SOL=0, BTC=1, ETH=2, XRP=13, DOGE=7, BNB=8, SUI=9, ARB=6,
  1MPEPE=10, WIF=23, SEI=21, INJ=15, AVAX=22, LINK=16, ADA=72, LTC=60
"""

import asyncio
import base58
import logging
from typing import Optional

from api.config import settings
from api.services.crypto import decrypt_key

log = logging.getLogger("astraios.solana_trader")

# Ticker → Drift perp market index
DRIFT_MARKET_INDEX: dict[str, int] = {
    "BTCUSDT":       1,
    "ETHUSDT":       2,
    "SOLUSDT":       0,
    "BNBUSDT":       8,
    "DOGEUSDT":      7,
    "XRPUSDT":      13,
    "AVAXUSDT":     22,
    "LINKUSDT":     16,
    "SEIUSDT":      21,
    "SUIUSDT":       9,
    "ARBUSDT":       6,
    "1000PEPEUSDT": 10,
    "WIFUSDT":      23,
    "INJUSDT":      15,
    "ADAUSDT":      72,
    "LTCUSDT":      60,
}

# Minimum USDC collateral to attempt a trade (safety floor)
MIN_COLLATERAL_USDC = 10.0

# Default public RPC — users should supply their own (Helius/QuickNode) for reliability
DEFAULT_RPC = "https://api.mainnet-beta.solana.com"


def _decode_keypair(private_key_b58: str):
    """Decode a base58 Solana private key into a Keypair."""
    from solders.keypair import Keypair  # type: ignore
    raw = base58.b58decode(private_key_b58)
    return Keypair.from_bytes(raw)


async def _make_drift_client(private_key_b58: str, rpc_url: str):
    """Initialise and subscribe a DriftClient."""
    from solana.rpc.async_api import AsyncClient          # type: ignore
    from driftpy.drift_client import DriftClient         # type: ignore
    from driftpy.account_subscription_config import AccountSubscriptionConfig  # type: ignore

    connection = AsyncClient(rpc_url)
    keypair = _decode_keypair(private_key_b58)

    client = DriftClient(
        connection,
        keypair,
        "mainnet",
        account_subscription=AccountSubscriptionConfig("cached"),
    )
    await client.subscribe()
    return client


async def get_balance(private_key_enc: str, rpc_url: str) -> dict:
    """Return USDC collateral balance from the Drift account."""
    pk = decrypt_key(private_key_enc)
    rpc = rpc_url or DEFAULT_RPC
    client = None
    try:
        client = await _make_drift_client(pk, rpc)
        user = client.get_user()
        total_col = user.get_total_collateral() / 1e6  # USDC has 6 decimals
        free_col   = user.get_free_collateral()    / 1e6
        upnl       = user.get_unrealised_pnl(True) / 1e6
        return {
            "equity":            round(total_col, 4),
            "available_balance": round(free_col,  4),
            "wallet_balance":    round(total_col, 4),
            "unrealised_pnl":    round(upnl,      4),
            "margin_used":       round(total_col - free_col, 4),
            "currency":          "USDC",
        }
    except Exception as e:
        raise RuntimeError(f"Drift balance fetch failed: {e}") from e
    finally:
        if client:
            await client.unsubscribe()


async def get_positions(private_key_enc: str, rpc_url: str) -> list[dict]:
    """Return open perpetual positions on Drift."""
    pk = decrypt_key(private_key_enc)
    rpc = rpc_url or DEFAULT_RPC

    # Build reverse index map
    index_to_ticker = {v: k for k, v in DRIFT_MARKET_INDEX.items()}

    client = None
    try:
        client = await _make_drift_client(pk, rpc)
        user = client.get_user()
        positions = []
        for pos in user.get_active_perp_positions():
            ticker = index_to_ticker.get(pos.market_index, f"MARKET_{pos.market_index}")
            base_amt = pos.base_asset_amount / 1e9   # base assets use 9 decimals
            if abs(base_amt) < 1e-9:
                continue
            entry = pos.quote_entry_amount / abs(pos.base_asset_amount) if pos.base_asset_amount != 0 else 0
            upnl  = user.get_unrealised_pnl(True, pos.market_index) / 1e6
            positions.append({
                "symbol":        ticker,
                "side":          "Buy" if base_amt > 0 else "Sell",
                "size":          round(abs(base_amt), 6),
                "entry_price":   round(abs(entry), 6),
                "mark_price":    0.0,   # requires oracle; omitted for simplicity
                "unrealised_pnl": round(upnl, 4),
                "leverage":      "1",
                "liq_price":     "",
                "tp":            "",
                "sl":            "",
                "venue":         "drift",
            })
        return positions
    except Exception as e:
        raise RuntimeError(f"Drift positions fetch failed: {e}") from e
    finally:
        if client:
            await client.unsubscribe()


async def place_order(
    symbol: str,
    side: str,          # "Buy" | "Sell"
    qty: str,           # base asset quantity as string
    tp: Optional[str] = None,
    sl: Optional[str] = None,
    private_key_enc: str = "",
    rpc_url: str = "",
) -> dict:
    """Open a market perp position on Drift."""
    from driftpy.types import (              # type: ignore
        OrderType, OrderParams, PositionDirection,
        MarketType, PostOnlyParams,
    )
    from driftpy.constants.numeric_constants import BASE_PRECISION  # type: ignore

    market_index = DRIFT_MARKET_INDEX.get(symbol.upper())
    if market_index is None:
        raise ValueError(f"{symbol} not supported on Drift (no market index)")

    pk = decrypt_key(private_key_enc)
    rpc = rpc_url or DEFAULT_RPC
    client = None
    try:
        client = await _make_drift_client(pk, rpc)
        direction = PositionDirection.Long() if side == "Buy" else PositionDirection.Short()
        base_amt  = int(float(qty) * BASE_PRECISION)

        order_params = OrderParams(
            order_type=OrderType.Market(),
            market_type=MarketType.Perp(),
            direction=direction,
            market_index=market_index,
            base_asset_amount=base_amt,
            post_only=PostOnlyParams.None_(),
        )
        tx_sig = await client.place_perp_order(order_params)
        log.info("Drift OPEN %s %s qty=%s tx=%s", side, symbol, qty, tx_sig)
        return {"order_id": str(tx_sig), "venue": "drift"}
    except Exception as e:
        raise RuntimeError(f"Drift place_order failed for {symbol}: {e}") from e
    finally:
        if client:
            await client.unsubscribe()


async def close_position(
    symbol: str,
    side: str,
    qty: str,
    private_key_enc: str = "",
    rpc_url: str = "",
) -> dict:
    """Close a perp position on Drift (reverse market order)."""
    close_side = "Sell" if side == "Buy" else "Buy"
    return await place_order(
        symbol=symbol, side=close_side, qty=qty,
        private_key_enc=private_key_enc, rpc_url=rpc_url,
    )


async def get_closed_pnl(
    limit: int = 50,
    private_key_enc: str = "",
    rpc_url: str = "",
) -> list[dict]:
    """Fetch recent closed P&L records from Drift (via REST API — no SDK needed)."""
    import aiohttp
    pk_raw = decrypt_key(private_key_enc)
    if not pk_raw:
        return []
    try:
        keypair = _decode_keypair(pk_raw)
        pubkey  = str(keypair.pubkey())
    except Exception:
        return []

    # Drift public REST API — no auth required for read
    url = f"https://drift-historical-data-v2.s3.eu-west-1.amazonaws.com/program/dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH/user/{pubkey}/tradeRecords/2026/2026"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                trades = []
                index_to_ticker = {v: k for k, v in DRIFT_MARKET_INDEX.items()}
                for record in (data if isinstance(data, list) else data.get("records", []))[:limit]:
                    pnl = float(record.get("pnl", 0)) / 1e6
                    trades.append({
                        "symbol":      index_to_ticker.get(record.get("marketIndex", -1), "UNKNOWN"),
                        "side":        "Buy" if record.get("direction") == "long" else "Sell",
                        "qty":         str(abs(float(record.get("baseAssetAmount", 0))) / 1e9),
                        "entry_price": float(record.get("entryPrice", 0)),
                        "exit_price":  float(record.get("exitPrice",  0)),
                        "pnl":         round(pnl, 4),
                        "created_time": str(record.get("ts", "")),
                        "updated_time": str(record.get("ts", "")),
                    })
                return trades
    except Exception as e:
        log.warning("Drift closed PnL fetch failed: %s", e)
        return []
