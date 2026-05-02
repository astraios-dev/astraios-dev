from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import get_db
from api.models.signal import Signal
from api.models.user import User
from api.schemas.signal import SignalCreate, SignalResponse
from api.services.auth import get_current_user

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("", response_model=list[SignalResponse])
async def list_signals(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Signal).where(Signal.user_id == user.id).order_by(Signal.created_at.desc())
    )
    return [
        SignalResponse(id=str(s.id), ticker=s.ticker, action=s.action,
                       confidence=s.confidence, rationale=s.rationale, created_at=s.created_at)
        for s in result.scalars()
    ]


@router.post("", response_model=SignalResponse, status_code=status.HTTP_201_CREATED)
async def create_signal(
    body: SignalCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    signal = Signal(
        user_id=user.id,
        ticker=body.ticker.upper(),
        action=body.action,
        confidence=body.confidence,
        rationale=body.rationale,
    )
    db.add(signal)
    await db.commit()
    await db.refresh(signal)
    return SignalResponse(
        id=str(signal.id), ticker=signal.ticker, action=signal.action,
        confidence=signal.confidence, rationale=signal.rationale, created_at=signal.created_at,
    )


@router.delete("/{signal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_signal(
    signal_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Signal).where(Signal.id == signal_id, Signal.user_id == user.id)
    )
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signal not found")
    await db.delete(signal)
    await db.commit()
