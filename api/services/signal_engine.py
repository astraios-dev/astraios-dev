"""
Lightweight signal engine.

Scores each ticker using a momentum + mean-reversion blend on the last 20 days
of daily returns. Produces BUY / SELL / HOLD with a confidence in [0, 1] and a
short rationale string.  No ML model — just clean heuristics that generate
non-trivial, time-varying signals from real price data.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import yfinance as yf

from api.services.market_data import ALL_DISPLAY_TICKERS, _yf_symbol

LOOKBACK = "1mo"


@dataclass
class SignalResult:
    ticker: str
    action: str          # BUY | SELL | HOLD
    confidence: float    # 0-1
    rationale: str


def _score_series(closes: np.ndarray) -> SignalResult | None:
    if len(closes) < 5:
        return None

    returns = np.diff(closes) / closes[:-1]
    mom_5 = float(np.sum(returns[-5:]))
    mom_20 = float(np.sum(returns)) if len(returns) >= 15 else mom_5

    vol = float(np.std(returns)) if len(returns) > 1 else 0.01
    z_score = (returns[-1] - float(np.mean(returns))) / vol if vol > 0 else 0

    trend_score = 0.6 * mom_5 + 0.4 * mom_20
    mean_rev = -0.3 * z_score

    composite = trend_score + mean_rev

    if composite > 0.015:
        action = "BUY"
    elif composite < -0.015:
        action = "SELL"
    else:
        action = "HOLD"

    confidence = min(abs(composite) / 0.06, 1.0)
    confidence = round(0.50 + confidence * 0.45, 2)

    pct_5d = round(mom_5 * 100, 1)
    direction = "up" if pct_5d >= 0 else "down"
    abs_z = round(abs(z_score), 1)

    parts = [f"5d momentum {direction} {abs(pct_5d)}%"]
    if abs_z > 1.2:
        parts.append(f"z-score {'+' if z_score > 0 else '-'}{abs_z} (extended)")
    if vol > 0.025:
        parts.append(f"elevated vol ({round(vol * 100, 1)}%)")
    rationale = ". ".join(parts) + "."

    return SignalResult(ticker="", action=action, confidence=confidence, rationale=rationale)


async def generate_signals(tickers: list[str] | None = None) -> list[SignalResult]:
    tickers = tickers or ALL_DISPLAY_TICKERS
    yf_symbols = [_yf_symbol(t) for t in tickers]
    display_map = dict(zip(yf_symbols, tickers))

    def _run():
        data = yf.download(yf_symbols, period=LOOKBACK, group_by="ticker", progress=False, threads=True)
        results = []
        for sym in yf_symbols:
            try:
                if len(yf_symbols) == 1:
                    df = data
                else:
                    df = data[sym]
                closes = df["Close"].dropna().values.flatten()
                sig = _score_series(closes)
                if sig:
                    sig.ticker = display_map[sym]
                    results.append(sig)
            except (KeyError, IndexError):
                continue
        return results

    return await asyncio.to_thread(_run)
