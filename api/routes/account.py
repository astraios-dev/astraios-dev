from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import get_db
from api.models.user import User
from api.models.signal import Signal
from api.models.position import Position
from api.services.auth import get_current_user

router = APIRouter(prefix="/account", tags=["account"])


class ApiKeysRequest(BaseModel):
    bybit_api_key: str
    bybit_api_secret: str


@router.get("/stats")
async def account_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    signal_count = await db.scalar(
        select(func.count()).select_from(Signal).where(Signal.user_id == user.id)
    )
    position_count = await db.scalar(
        select(func.count()).select_from(Position).where(Position.user_id == user.id)
    )

    result = await db.execute(
        select(Position).where(Position.user_id == user.id)
    )
    positions = result.scalars().all()

    import math
    portfolio_value = sum((p.current_price or p.entry_price) * p.quantity for p in positions if not (isinstance(p.current_price, float) and math.isnan(p.current_price)))
    total_pnl = sum(((p.current_price or p.entry_price) - p.entry_price) * p.quantity for p in positions if not (isinstance(p.current_price, float) and math.isnan(p.current_price)))

    return {
        "email": user.email,
        "name": user.name,
        "plan": user.plan,
        "execution_mode": "Live (Bybit)" if user.bybit_api_key else "Paper",
        "api_access": True,
        "has_api_keys": bool(user.bybit_api_key),
        "api_key_hint": f"...{user.bybit_api_key[-4:]}" if user.bybit_api_key else None,
        "has_testnet_keys": bool(user.bybit_testnet_key),
        "testnet_key_hint": f"...{user.bybit_testnet_key[-4:]}" if user.bybit_testnet_key else None,
        "total_signals": signal_count,
        "open_positions": position_count,
        "portfolio_value": round(portfolio_value, 2),
        "total_pnl": round(total_pnl, 2),
    }


@router.post("/api-keys")
async def save_api_keys(
    body: ApiKeysRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user.bybit_api_key = body.bybit_api_key
    user.bybit_api_secret = body.bybit_api_secret
    await db.commit()
    return {"status": "ok", "api_key_hint": f"...{body.bybit_api_key[-4:]}"}


@router.delete("/api-keys")
async def remove_api_keys(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user.bybit_api_key = None
    user.bybit_api_secret = None
    await db.commit()
    return {"status": "ok"}


@router.post("/testnet-keys")
async def save_testnet_keys(
    body: ApiKeysRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user.bybit_testnet_key = body.bybit_api_key
    user.bybit_testnet_secret = body.bybit_api_secret
    await db.commit()
    return {"status": "ok", "testnet_key_hint": f"...{body.bybit_api_key[-4:]}"}


@router.delete("/testnet-keys")
async def remove_testnet_keys(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user.bybit_testnet_key = None
    user.bybit_testnet_secret = None
    await db.commit()
    return {"status": "ok"}


@router.get("/model-info")
async def model_info(user: User = Depends(get_current_user)):
    import os, json
    model_dir = os.path.join(os.path.dirname(__file__), "../../ml/output")
    config_path = os.path.join(model_dir, "config.json")
    model_path = os.path.join(model_dir, "model.pt")
    if not os.path.exists(config_path) or not os.path.exists(model_path):
        return {"engine": "heuristic", "model_loaded": False}
    with open(config_path) as f:
        cfg = json.load(f)
    return {
        "engine": "transformer",
        "model_loaded": True,
        "val_acc": round(cfg.get("best_val_acc", 0) * 100, 1),
        "n_features": cfg.get("n_features"),
        "d_model": cfg.get("d_model"),
        "n_layers": cfg.get("n_layers"),
        "seq_len": cfg.get("seq_len"),
    }
