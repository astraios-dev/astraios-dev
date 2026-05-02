import asyncio
import math
from datetime import datetime, timezone
import yfinance as yf

EQUITY_TICKERS = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "TSLA", "META", "AMD"]

CRYPTO_TICKERS = {
    "SOL/USD": "SOL-USD",
    "ETH/USD": "ETH-USD",
    "BTC/USD": "BTC-USD",
}

ALL_DISPLAY_TICKERS = EQUITY_TICKERS + list(CRYPTO_TICKERS.keys())


def _yf_symbol(ticker: str) -> str:
    return CRYPTO_TICKERS.get(ticker, ticker)


async def fetch_prices(tickers: list[str] | None = None) -> dict[str, dict]:
    tickers = tickers or ALL_DISPLAY_TICKERS
    yf_symbols = [_yf_symbol(t) for t in tickers]
    display_map = dict(zip(yf_symbols, tickers))

    def _download():
        data = yf.download(yf_symbols, period="5d", group_by="ticker", progress=False, threads=True)
        result = {}
        for sym in yf_symbols:
            try:
                if len(yf_symbols) == 1:
                    df = data
                else:
                    df = data[sym]
                if df.empty:
                    continue
                last = df.iloc[-1]
                prev = df.iloc[-2] if len(df) > 1 else last
                close_val = float(last["Close"].iloc[0]) if hasattr(last["Close"], "iloc") else float(last["Close"])
                prev_val = float(prev["Close"].iloc[0]) if hasattr(prev["Close"], "iloc") else float(prev["Close"])
                if math.isnan(close_val) or math.isnan(prev_val):
                    continue
                result[display_map[sym]] = {
                    "price": round(close_val, 2),
                    "prev_close": round(prev_val, 2),
                    "change_pct": round(((close_val - prev_val) / prev_val) * 100, 2) if prev_val else 0,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }
            except (KeyError, IndexError):
                continue
        return result

    return await asyncio.to_thread(_download)


async def fetch_price(ticker: str) -> float | None:
    prices = await fetch_prices([ticker])
    entry = prices.get(ticker)
    return entry["price"] if entry else None
