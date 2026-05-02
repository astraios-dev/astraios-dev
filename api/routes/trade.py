from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pybit.exceptions import FailedRequestError

from api.models.user import User
from api.services.auth import get_current_user
from api.services import bybit

router = APIRouter(prefix="/trade", tags=["trade"])


class OrderRequest(BaseModel):
    symbol: str
    side: str
    qty: str
    tp: str | None = None
    sl: str | None = None


class CloseRequest(BaseModel):
    symbol: str
    side: str
    qty: str


class LeverageRequest(BaseModel):
    symbol: str
    leverage: str


@router.get("/positions")
async def positions(
    symbol: str | None = None,
    user: User = Depends(get_current_user),
):
    try:
        return await bybit.get_positions(symbol)
    except (RuntimeError, FailedRequestError) as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/orders")
async def open_orders(
    symbol: str | None = None,
    user: User = Depends(get_current_user),
):
    try:
        return await bybit.get_open_orders(symbol)
    except (RuntimeError, FailedRequestError) as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/wallet")
async def wallet(user: User = Depends(get_current_user)):
    try:
        return await bybit.get_wallet_balance()
    except (RuntimeError, FailedRequestError) as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/order")
async def place_order(body: OrderRequest, user: User = Depends(get_current_user)):
    if body.side not in ("Buy", "Sell"):
        raise HTTPException(status_code=422, detail="side must be Buy or Sell")
    try:
        return await bybit.place_order(
            symbol=body.symbol.upper(),
            side=body.side,
            qty=body.qty,
            tp=body.tp,
            sl=body.sl,
        )
    except (RuntimeError, FailedRequestError) as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/close")
async def close_position(body: CloseRequest, user: User = Depends(get_current_user)):
    try:
        return await bybit.close_position(
            symbol=body.symbol.upper(),
            side=body.side,
            qty=body.qty,
        )
    except (RuntimeError, FailedRequestError) as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/leverage")
async def set_leverage(body: LeverageRequest, user: User = Depends(get_current_user)):
    try:
        return await bybit.set_leverage(
            symbol=body.symbol.upper(),
            leverage=body.leverage,
        )
    except (RuntimeError, FailedRequestError) as e:
        raise HTTPException(status_code=502, detail=str(e))
