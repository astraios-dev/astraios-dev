from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import get_db
from api.models.position import Position
from api.models.user import User
from api.schemas.position import PositionCreate, PositionUpdate, PositionResponse
from api.services.auth import get_current_user

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


def _to_response(p: Position) -> PositionResponse:
    cp = p.current_price if p.current_price and not (isinstance(p.current_price, float) and p.current_price != p.current_price) else p.entry_price
    pnl = (cp - p.entry_price) * p.quantity
    pnl_pct = ((cp - p.entry_price) / p.entry_price) * 100 if p.entry_price else 0
    return PositionResponse(
        id=str(p.id), ticker=p.ticker, quantity=p.quantity,
        entry_price=p.entry_price, current_price=round(cp, 2),
        pnl=round(pnl, 2), pnl_pct=round(pnl_pct, 2),
        created_at=p.created_at, updated_at=p.updated_at,
    )


@router.get("", response_model=list[PositionResponse])
async def list_positions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Position).where(Position.user_id == user.id).order_by(Position.created_at.desc())
    )
    return [_to_response(p) for p in result.scalars()]


@router.post("", response_model=PositionResponse, status_code=status.HTTP_201_CREATED)
async def create_position(
    body: PositionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    position = Position(
        user_id=user.id,
        ticker=body.ticker.upper(),
        quantity=body.quantity,
        entry_price=body.entry_price,
        current_price=body.current_price,
    )
    db.add(position)
    await db.commit()
    await db.refresh(position)
    return _to_response(position)


@router.patch("/{position_id}", response_model=PositionResponse)
async def update_position(
    position_id: UUID,
    body: PositionUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Position).where(Position.id == position_id, Position.user_id == user.id)
    )
    position = result.scalar_one_or_none()
    if not position:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position not found")

    if body.quantity is not None:
        position.quantity = body.quantity
    if body.current_price is not None:
        position.current_price = body.current_price

    await db.commit()
    await db.refresh(position)
    return _to_response(position)


@router.delete("/{position_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_position(
    position_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Position).where(Position.id == position_id, Position.user_id == user.id)
    )
    position = result.scalar_one_or_none()
    if not position:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position not found")
    await db.delete(position)
    await db.commit()
