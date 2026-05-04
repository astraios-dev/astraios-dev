"""
Background scheduler that runs on app startup.

Two recurring jobs:
  1. refresh_signals  — generate signals from Bybit klines for every user (every 15 min)
  2. refresh_prices   — update current_price on paper positions via yfinance (every 5 min)
"""

import asyncio
import logging

from sqlalchemy import select, update

from api.db import async_session
from api.models.signal import Signal
from api.models.position import Position
from api.models.user import User
from api.services.market_data import fetch_prices
from api.services.signal_engine import generate_signals
from api.services import auto_trader

log = logging.getLogger("astraios.scheduler")

_running = False


async def refresh_signals():
    try:
        signals = await generate_signals()
        if not signals:
            log.warning("signal engine returned no results")
            return

        async with async_session() as db:
            users = (await db.execute(select(User.id))).scalars().all()

            for user_id in users:
                for sig in signals:
                    db.add(Signal(
                        user_id=user_id,
                        ticker=sig.ticker,
                        action=sig.action,
                        confidence=sig.confidence,
                        rationale=sig.rationale,
                    ))
            await db.commit()
        log.info("refreshed signals: %d symbols × %d users", len(signals), len(users))

        # Run auto-trader after signals are written
        await auto_trader.run_all(signals)
    except Exception:
        log.exception("signal refresh failed")


async def refresh_prices():
    try:
        async with async_session() as db:
            tickers_result = await db.execute(
                select(Position.ticker).distinct()
            )
            tickers = tickers_result.scalars().all()
            if not tickers:
                return

            prices = await fetch_prices(list(tickers))

            for ticker, data in prices.items():
                await db.execute(
                    update(Position)
                    .where(Position.ticker == ticker)
                    .values(current_price=data["price"])
                )
            await db.commit()
        log.info("refreshed prices for %d tickers", len(prices))
    except Exception:
        log.exception("price refresh failed")


async def _loop(coro, interval_seconds: int, name: str):
    while _running:
        log.info("running %s", name)
        await coro()
        await asyncio.sleep(interval_seconds)


async def start():
    global _running
    _running = True
    asyncio.create_task(_loop(refresh_signals, 15 * 60, "refresh_signals"))
    asyncio.create_task(_loop(refresh_prices, 5 * 60, "refresh_prices"))
    log.info("scheduler started — signals every 15m, prices every 5m")


def stop():
    global _running
    _running = False
    log.info("scheduler stopped")
