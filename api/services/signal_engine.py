"""
Signal engine powered by Bybit kline data.

For each symbol, fetches 1h and 4h candles and scores them on:
  - EMA crossover (8/21)
  - RSI (14) overbought/oversold
  - MACD histogram direction
  - Volume spike detection
  - ATR-normalised momentum

Produces BUY / SELL / HOLD with confidence and a rationale string.
"""

import asyncio
from dataclasses import dataclass

import numpy as np
from pybit.unified_trading import HTTP

from api.config import settings

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "SUIUSDT",
    "DOGEUSDT", "XRPUSDT", "LINKUSDT", "AAVEUSDT",
    "1000PEPEUSDT", "WIFUSDT", "ARBUSDT", "AVAXUSDT",
]


@dataclass
class SignalResult:
    ticker: str
    action: str
    confidence: float
    rationale: str


def _client() -> HTTP:
    c = HTTP()
    if settings.bybit_proxy:
        c.client.proxies = {
            "http": settings.bybit_proxy,
            "https": settings.bybit_proxy,
        }
    return c


def _parse_klines(raw: list) -> dict[str, np.ndarray]:
    rows = list(reversed(raw))
    return {
        "open": np.array([float(r[1]) for r in rows]),
        "high": np.array([float(r[2]) for r in rows]),
        "low": np.array([float(r[3]) for r in rows]),
        "close": np.array([float(r[4]) for r in rows]),
        "volume": np.array([float(r[5]) for r in rows]),
    }


def _ema(data: np.ndarray, period: int) -> np.ndarray:
    alpha = 2 / (period + 1)
    out = np.empty_like(data)
    out[0] = data[0]
    for i in range(1, len(data)):
        out[i] = alpha * data[i] + (1 - alpha) * out[i - 1]
    return out


def _rsi(closes: np.ndarray, period: int = 14) -> float:
    deltas = np.diff(closes[-(period + 1):])
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains) if len(gains) else 0
    avg_loss = np.mean(losses) if len(losses) else 1e-9
    rs = avg_gain / max(avg_loss, 1e-9)
    return 100 - (100 / (1 + rs))


def _macd(closes: np.ndarray) -> tuple[float, float]:
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd_line = ema12 - ema26
    signal_line = _ema(macd_line, 9)
    histogram = macd_line[-1] - signal_line[-1]
    prev_hist = macd_line[-2] - signal_line[-2] if len(macd_line) > 1 else histogram
    return float(histogram), float(histogram - prev_hist)


def _atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
    tr = np.maximum(
        highs[-period:] - lows[-period:],
        np.maximum(
            np.abs(highs[-period:] - closes[-period - 1:-1]),
            np.abs(lows[-period:] - closes[-period - 1:-1]),
        ),
    )
    return float(np.mean(tr))


def _score_symbol(k1h: dict[str, np.ndarray], k4h: dict[str, np.ndarray]) -> SignalResult | None:
    c1 = k1h["close"]
    c4 = k4h["close"]
    if len(c1) < 30 or len(c4) < 30:
        return None

    signals = []
    reasons = []

    # 1. EMA crossover on 1h (fast trend)
    ema8 = _ema(c1, 8)
    ema21 = _ema(c1, 21)
    ema_diff = (ema8[-1] - ema21[-1]) / c1[-1] * 100
    if ema_diff > 0.15:
        signals.append(0.25)
        reasons.append(f"1h EMA8 > EMA21 (+{ema_diff:.2f}%)")
    elif ema_diff < -0.15:
        signals.append(-0.25)
        reasons.append(f"1h EMA8 < EMA21 ({ema_diff:.2f}%)")
    else:
        signals.append(0)

    # 2. RSI on 4h (regime)
    rsi = _rsi(c4, 14)
    if rsi > 70:
        signals.append(-0.2)
        reasons.append(f"4h RSI {rsi:.0f} (overbought)")
    elif rsi < 30:
        signals.append(0.2)
        reasons.append(f"4h RSI {rsi:.0f} (oversold)")
    elif rsi > 55:
        signals.append(0.1)
        reasons.append(f"4h RSI {rsi:.0f} (bullish)")
    elif rsi < 45:
        signals.append(-0.1)
        reasons.append(f"4h RSI {rsi:.0f} (bearish)")
    else:
        signals.append(0)
        reasons.append(f"4h RSI {rsi:.0f} (neutral)")

    # 3. MACD on 4h (momentum)
    hist, hist_delta = _macd(c4)
    atr = _atr(k4h["high"], k4h["low"], c4) or 1
    norm_hist = hist / atr
    if norm_hist > 0.1 and hist_delta > 0:
        signals.append(0.25)
        reasons.append("4h MACD histogram expanding bullish")
    elif norm_hist < -0.1 and hist_delta < 0:
        signals.append(-0.25)
        reasons.append("4h MACD histogram expanding bearish")
    elif hist_delta > 0:
        signals.append(0.1)
    elif hist_delta < 0:
        signals.append(-0.1)

    # 4. Volume spike on 1h
    vol = k1h["volume"]
    vol_ma = float(np.mean(vol[-20:])) if len(vol) >= 20 else float(np.mean(vol))
    vol_ratio = vol[-1] / max(vol_ma, 1e-9)
    if vol_ratio > 2.0:
        last_return = (c1[-1] - c1[-2]) / c1[-2]
        direction = 0.15 if last_return > 0 else -0.15
        signals.append(direction)
        reasons.append(f"1h volume spike {vol_ratio:.1f}x avg")

    # 5. ATR-normalised momentum on 4h (5-bar)
    mom = (c4[-1] - c4[-5]) / atr
    if abs(mom) > 0.5:
        s = 0.2 if mom > 0 else -0.2
        signals.append(s)
        reasons.append(f"4h momentum {'up' if mom > 0 else 'down'} {abs(mom):.1f} ATR")

    composite = sum(signals)

    if composite > 0.15:
        action = "BUY"
    elif composite < -0.15:
        action = "SELL"
    else:
        action = "HOLD"

    confidence = min(abs(composite) / 0.8, 1.0)
    confidence = round(0.50 + confidence * 0.45, 2)

    rationale = ". ".join(reasons[:3]) + "." if reasons else "Insufficient data."

    return SignalResult(ticker="", action=action, confidence=confidence, rationale=rationale)


def _fetch_and_score(client: HTTP, symbol: str) -> SignalResult | None:
    try:
        r1 = client.get_kline(category="linear", symbol=symbol, interval="60", limit=100)
        r4 = client.get_kline(category="linear", symbol=symbol, interval="240", limit=100)
        if r1["retCode"] != 0 or r4["retCode"] != 0:
            return None
        k1h = _parse_klines(r1["result"]["list"])
        k4h = _parse_klines(r4["result"]["list"])
        sig = _score_symbol(k1h, k4h)
        if sig:
            sig.ticker = symbol
        return sig
    except Exception:
        return None


async def generate_signals(symbols: list[str] | None = None) -> list[SignalResult]:
    symbols = symbols or SYMBOLS

    def _run():
        client = _client()
        results = []
        for sym in symbols:
            sig = _fetch_and_score(client, sym)
            if sig:
                results.append(sig)
        return results

    return await asyncio.to_thread(_run)
