import re
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, field_validator
from pybit.exceptions import FailedRequestError

from api.limiter import limiter
from api.models.user import User
from api.services.auth import get_current_user
from api.services import bybit

router = APIRouter(prefix="/trade", tags=["trade"])

_SYMBOL_RE = re.compile(r"^[A-Z0-9]{2,20}USDT$")


def _keys(user: User, demo: bool = False) -> dict:
    if demo:
        # Demo keys are stored in the testnet fields, routed via api-demo.bybit.com
        return {"api_key": user.bybit_testnet_key, "api_secret": user.bybit_testnet_secret,
                "testnet": False, "demo": True}
    return {"api_key": user.bybit_api_key, "api_secret": user.bybit_api_secret,
            "testnet": False, "demo": False}


def _validate_symbol(v: str) -> str:
    v = v.upper().strip()
    if not _SYMBOL_RE.match(v):
        raise ValueError("symbol must be a valid USDT perpetual (e.g. BTCUSDT)")
    return v


def _validate_qty(v: str) -> str:
    try:
        qty = float(v)
    except ValueError:
        raise ValueError("qty must be a number")
    if qty <= 0:
        raise ValueError("qty must be positive")
    return v


class OrderRequest(BaseModel):
    symbol: str
    side: str
    qty: str
    tp: str | None = None
    sl: str | None = None
    demo: bool = False

    @field_validator("symbol")
    @classmethod
    def check_symbol(cls, v): return _validate_symbol(v)

    @field_validator("side")
    @classmethod
    def check_side(cls, v):
        if v not in ("Buy", "Sell"):
            raise ValueError("side must be Buy or Sell")
        return v

    @field_validator("qty")
    @classmethod
    def check_qty(cls, v): return _validate_qty(v)


class CloseRequest(BaseModel):
    symbol: str
    side: str
    qty: str
    demo: bool = False

    @field_validator("symbol")
    @classmethod
    def check_symbol(cls, v): return _validate_symbol(v)

    @field_validator("qty")
    @classmethod
    def check_qty(cls, v): return _validate_qty(v)


class LeverageRequest(BaseModel):
    symbol: str
    leverage: str
    demo: bool = False

    @field_validator("symbol")
    @classmethod
    def check_symbol(cls, v): return _validate_symbol(v)

    @field_validator("leverage")
    @classmethod
    def check_leverage(cls, v):
        try:
            lev = int(v)
        except ValueError:
            raise ValueError("leverage must be an integer")
        if not (1 <= lev <= 100):
            raise ValueError("leverage must be between 1 and 100")
        return v


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
    demo: bool = Query(False),
    user: User = Depends(get_current_user),
):
    try:
        return await bybit.get_positions(symbol, **_keys(user, demo))
    except (RuntimeError, FailedRequestError) as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/orders")
async def open_orders(
    symbol: str | None = None,
    demo: bool = Query(False),
    user: User = Depends(get_current_user),
):
    try:
        return await bybit.get_open_orders(symbol, **_keys(user, demo))
    except (RuntimeError, FailedRequestError) as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/wallet")
async def wallet(
    demo: bool = Query(False),
    user: User = Depends(get_current_user),
):
    try:
        return await bybit.get_wallet_balance(**_keys(user, demo))
    except (RuntimeError, FailedRequestError) as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/order")
@limiter.limit("10/minute")
async def place_order(request: Request, body: OrderRequest, user: User = Depends(get_current_user)):
    try:
        return await bybit.place_order(
            symbol=body.symbol.upper(),
            side=body.side,
            qty=body.qty,
            tp=body.tp,
            sl=body.sl,
            **_keys(user, body.demo),
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
            **_keys(user, body.demo),
        )
    except (RuntimeError, FailedRequestError) as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/leverage")
async def set_leverage(body: LeverageRequest, user: User = Depends(get_current_user)):
    try:
        return await bybit.set_leverage(
            symbol=body.symbol.upper(),
            leverage=body.leverage,
            **_keys(user, body.demo),
        )
    except (RuntimeError, FailedRequestError) as e:
        raise HTTPException(status_code=502, detail=str(e))
