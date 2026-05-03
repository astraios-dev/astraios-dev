from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from pybit.exceptions import FailedRequestError

from api.models.user import User
from api.services.auth import get_current_user
from api.services import bybit

router = APIRouter(prefix="/trade", tags=["trade"])


def _keys(user: User, testnet: bool = False) -> dict:
    if testnet:
        return {"api_key": user.bybit_testnet_key, "api_secret": user.bybit_testnet_secret, "testnet": True}
    return {"api_key": user.bybit_api_key, "api_secret": user.bybit_api_secret, "testnet": False}


class OrderRequest(BaseModel):
    symbol: str
    side: str
    qty: str
    tp: str | None = None
    sl: str | None = None
    testnet: bool = False


class CloseRequest(BaseModel):
    symbol: str
    side: str
    qty: str
    testnet: bool = False


class LeverageRequest(BaseModel):
    symbol: str
    leverage: str
    testnet: bool = False


@router.get("/klines")
async def klines(
    symbol: str,
    interval: str = "60",
    limit: int = Query(200, le=1000),
    user: User = Depends(get_current_user),
):
    try:
        return await bybit.get_klines(symbol=symbol.upper(), interval=interval, limit=limit)
    except (RuntimeError, FailedRequestError) as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/symbols")
async def symbols(user: User = Depends(get_current_user)):
    try:
        return await bybit.get_symbols()
    except (RuntimeError, FailedRequestError) as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/positions")
async def positions(
    symbol: str | None = None,
    testnet: bool = Query(False),
    user: User = Depends(get_current_user),
):
    try:
        return await bybit.get_positions(symbol, **_keys(user, testnet))
    except (RuntimeError, FailedRequestError) as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/orders")
async def open_orders(
    symbol: str | None = None,
    testnet: bool = Query(False),
    user: User = Depends(get_current_user),
):
    try:
        return await bybit.get_open_orders(symbol, **_keys(user, testnet))
    except (RuntimeError, FailedRequestError) as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/wallet")
async def wallet(
    testnet: bool = Query(False),
    user: User = Depends(get_current_user),
):
    try:
        return await bybit.get_wallet_balance(**_keys(user, testnet))
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
            **_keys(user, body.testnet),
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
            **_keys(user, body.testnet),
        )
    except (RuntimeError, FailedRequestError) as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/leverage")
async def set_leverage(body: LeverageRequest, user: User = Depends(get_current_user)):
    try:
        return await bybit.set_leverage(
            symbol=body.symbol.upper(),
            leverage=body.leverage,
            **_keys(user, body.testnet),
        )
    except (RuntimeError, FailedRequestError) as e:
        raise HTTPException(status_code=502, detail=str(e))
