from collections import defaultdict
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import get_db
from api.models.user import User
from api.models.auto_trade import AutoTradeConfig, AutoTradeLog
from api.services.auth import get_current_user
from api.services import bybit
from api.services.crypto import decrypt_key

router = APIRouter(prefix="/auto-trade", tags=["auto-trade"])


class AutoTradeConfigRequest(BaseModel):
    enabled: bool
    demo: bool = True
    confidence_threshold: float = Field(default=0.65, ge=0.5, le=1.0)
    max_positions: int = Field(default=3, ge=1, le=10)
    position_size_pct: float = Field(default=5.0, ge=0.1, le=50.0)
    leverage: int = Field(default=1, ge=1, le=20)
    tp_pct: float = Field(default=3.0, ge=0.1, le=100.0)
    sl_pct: float = Field(default=1.5, ge=0.1, le=100.0)
    daily_loss_limit: float = Field(default=50.0, ge=1.0)
    symbols: str = "BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,DOGEUSDT,LTCUSDT,TRXUSDT,XRPUSDT"


@router.get("/config")
async def get_config(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AutoTradeConfig).where(AutoTradeConfig.user_id == user.id)
    )
    cfg = result.scalar_one_or_none()
    if cfg is None:
        return {
            "enabled": False,
            "demo": True,
            "confidence_threshold": 0.65,
            "max_positions": 3,
            "position_size_pct": 5.0,
            "leverage": 1,
            "tp_pct": 3.0,
            "sl_pct": 1.5,
            "daily_loss_limit": 50.0,
            "symbols": "BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,DOGEUSDT,LTCUSDT,TRXUSDT,XRPUSDT",
        }
    return {
        "enabled": cfg.enabled,
        "demo": cfg.demo,
        "confidence_threshold": cfg.confidence_threshold,
        "max_positions": cfg.max_positions,
        "position_size_pct": cfg.position_size_pct,
        "leverage": cfg.leverage,
        "tp_pct": cfg.tp_pct,
        "sl_pct": cfg.sl_pct,
        "daily_loss_limit": cfg.daily_loss_limit,
        "symbols": cfg.symbols,
    }


@router.post("/config")
async def save_config(
    body: AutoTradeConfigRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AutoTradeConfig).where(AutoTradeConfig.user_id == user.id)
    )
    cfg = result.scalar_one_or_none()
    if cfg is None:
        cfg = AutoTradeConfig(user_id=user.id)
        db.add(cfg)

    cfg.enabled = body.enabled
    cfg.demo = body.demo
    cfg.confidence_threshold = body.confidence_threshold
    cfg.max_positions = body.max_positions
    cfg.position_size_pct = body.position_size_pct
    cfg.leverage = body.leverage
    cfg.tp_pct = body.tp_pct
    cfg.sl_pct = body.sl_pct
    cfg.daily_loss_limit = body.daily_loss_limit
    cfg.symbols = body.symbols

    await db.commit()
    return {"status": "ok", "enabled": cfg.enabled}


@router.get("/stats")
async def trade_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AutoTradeLog)
        .where(AutoTradeLog.user_id == user.id)
        .order_by(AutoTradeLog.created_at.asc())
    )
    logs = result.scalars().all()

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)

    total_orders = 0
    filled = 0
    errors = 0
    today_orders = 0
    today_errors = 0
    by_symbol = defaultdict(lambda: {"filled": 0, "errors": 0})
    by_side = {"Buy": 0, "Sell": 0}
    conf_sum = 0.0
    conf_count = 0

    # Pair opens → closes to compute hold times
    open_times = {}   # symbol → open datetime
    hold_times = []

    for l in logs:
        total_orders += 1
        created = l.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)

        is_today = created >= today

        if l.status == "filled":
            filled += 1
            by_symbol[l.symbol]["filled"] += 1
            by_side[l.side] = by_side.get(l.side, 0) + 1
            conf_sum += l.confidence
            conf_count += 1
            if is_today:
                today_orders += 1

            if l.action == "OPEN":
                open_times[l.symbol] = created
            elif l.action == "CLOSE" and l.symbol in open_times:
                hold_minutes = (created - open_times[l.symbol]).total_seconds() / 60
                hold_times.append(hold_minutes)
                del open_times[l.symbol]
        else:
            errors += 1
            by_symbol[l.symbol]["errors"] += 1
            if is_today:
                today_errors += 1

    # Active positions (opened but not yet closed)
    active = len(open_times)
    avg_conf = round(conf_sum / conf_count * 100, 1) if conf_count else 0
    avg_hold_min = round(sum(hold_times) / len(hold_times), 0) if hold_times else 0
    success_rate = round(filled / total_orders * 100, 1) if total_orders else 0

    top_symbols = sorted(
        [{"symbol": s, **v} for s, v in by_symbol.items()],
        key=lambda x: -x["filled"]
    )[:5]

    return {
        "total_orders": total_orders,
        "filled": filled,
        "errors": errors,
        "success_rate": success_rate,
        "today_orders": today_orders,
        "today_errors": today_errors,
        "active_positions": active,
        "avg_confidence": avg_conf,
        "avg_hold_minutes": avg_hold_min,
        "by_side": by_side,
        "top_symbols": top_symbols,
    }


@router.get("/pnl")
async def closed_pnl(
    limit: int = 50,
    demo: bool = False,
    user: User = Depends(get_current_user),
):
    if demo:
        api_key = decrypt_key(user.bybit_testnet_key)
        api_secret = decrypt_key(user.bybit_testnet_secret)
    else:
        api_key = decrypt_key(user.bybit_api_key)
        api_secret = decrypt_key(user.bybit_api_secret)

    if not api_key or not api_secret:
        return []

    try:
        trades = await bybit.get_closed_pnl(limit=limit, api_key=api_key, api_secret=api_secret, demo=demo)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    total_pnl = sum(t["pnl"] for t in trades)
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] < 0]

    return {
        "trades": trades,
        "summary": {
            "total_pnl": round(total_pnl, 4),
            "trade_count": len(trades),
            "win_count": len(wins),
            "loss_count": len(losses),
            "win_rate": round(len(wins) / len(trades) * 100, 1) if trades else 0,
            "avg_win": round(sum(t["pnl"] for t in wins) / len(wins), 4) if wins else 0,
            "avg_loss": round(sum(t["pnl"] for t in losses) / len(losses), 4) if losses else 0,
            "largest_win": round(max((t["pnl"] for t in wins), default=0), 4),
            "largest_loss": round(min((t["pnl"] for t in losses), default=0), 4),
        },
    }


@router.get("/log")
async def trade_log(
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AutoTradeLog)
        .where(AutoTradeLog.user_id == user.id)
        .order_by(AutoTradeLog.created_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()
    return [
        {
            "id": str(l.id),
            "symbol": l.symbol,
            "action": l.action,
            "side": l.side,
            "qty": l.qty,
            "confidence": l.confidence,
            "order_id": l.order_id,
            "status": l.status,
            "error": l.error,
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]
