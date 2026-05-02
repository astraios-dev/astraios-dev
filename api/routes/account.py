from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import get_db
from api.models.user import User
from api.models.signal import Signal
from api.models.position import Position
from api.services.auth import get_current_user

router = APIRouter(prefix="/account", tags=["account"])


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

    portfolio_value = sum(p.current_price * p.quantity for p in positions)
    total_pnl = sum((p.current_price - p.entry_price) * p.quantity for p in positions)

    return {
        "email": user.email,
        "name": user.name,
        "plan": user.plan,
        "execution_mode": "Paper (Alpaca sandbox)",
        "api_access": True,
        "total_signals": signal_count,
        "open_positions": position_count,
        "portfolio_value": round(portfolio_value, 2),
        "total_pnl": round(total_pnl, 2),
    }
