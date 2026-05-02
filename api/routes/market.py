from fastapi import APIRouter, Depends
from api.models.user import User
from api.services.auth import get_current_user
from api.services.market_data import fetch_prices, ALL_DISPLAY_TICKERS
from api.services.signal_engine import generate_signals
from api.services.scheduler import refresh_signals, refresh_prices

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/prices")
async def market_prices(user: User = Depends(get_current_user)):
    prices = await fetch_prices()
    return {"tickers": prices}


@router.post("/refresh")
async def trigger_refresh(user: User = Depends(get_current_user)):
    await refresh_signals()
    await refresh_prices()
    return {"status": "ok", "message": "Signals generated and prices updated."}
