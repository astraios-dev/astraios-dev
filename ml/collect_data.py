"""
Fetch historical kline data from Bybit and build a training dataset.

For each symbol, pulls 1000 candles across 1h and 4h timeframes,
engineers features, labels forward returns, and saves to CSV.
"""

import sys
import os
import time
import numpy as np
import pandas as pd
from pybit.unified_trading import HTTP

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from api.config import settings

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "SUIUSDT",
    "DOGEUSDT", "XRPUSDT", "LINKUSDT", "AAVEUSDT",
    "AVAXUSDT", "ARBUSDT", "WIFUSDT",
]

INTERVALS = {"60": "1h", "240": "4h"}
FORWARD_BARS = 6
BUY_THRESH = 0.01
SELL_THRESH = -0.01


def get_client():
    c = HTTP()
    if settings.bybit_proxy:
        c.client.proxies = {"http": settings.bybit_proxy, "https": settings.bybit_proxy}
    return c


def fetch_klines(client, symbol, interval, limit=1000):
    all_rows = []
    remaining = limit
    end_time = None
    while remaining > 0:
        batch = min(remaining, 200)
        params = {"category": "linear", "symbol": symbol, "interval": interval, "limit": batch}
        if end_time:
            params["end"] = end_time
        resp = client.get_kline(**params)
        if resp["retCode"] != 0:
            break
        rows = resp["result"]["list"]
        if not rows:
            break
        all_rows.extend(rows)
        end_time = int(rows[-1][0]) - 1
        remaining -= len(rows)
        if len(rows) < batch:
            break
        time.sleep(0.1)

    seen = set()
    candles = []
    for r in reversed(all_rows):
        ts = int(r[0])
        if ts in seen:
            continue
        seen.add(ts)
        candles.append({
            "timestamp": ts,
            "open": float(r[1]),
            "high": float(r[2]),
            "low": float(r[3]),
            "close": float(r[4]),
            "volume": float(r[5]),
        })
    return pd.DataFrame(candles)


def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))


def engineer_features(df):
    c = df["close"]
    h = df["high"]
    l = df["low"]
    v = df["volume"]

    df["returns"] = c.pct_change()
    df["log_returns"] = np.log(c / c.shift(1))

    for p in [8, 21, 50]:
        df[f"ema_{p}"] = ema(c, p)
        df[f"ema_ratio_{p}"] = c / df[f"ema_{p}"]

    df["ema_cross_8_21"] = df["ema_8"] - df["ema_21"]

    df["rsi_14"] = rsi(c, 14)
    df["rsi_7"] = rsi(c, 7)

    ema12 = ema(c, 12)
    ema26 = ema(c, 26)
    df["macd"] = ema12 - ema26
    df["macd_signal"] = ema(df["macd"], 9)
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    bb_mid = c.rolling(20).mean()
    bb_std = c.rolling(20).std()
    df["bb_upper"] = bb_mid + 2 * bb_std
    df["bb_lower"] = bb_mid - 2 * bb_std
    df["bb_pct"] = (c - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"]).replace(0, 1e-9)

    tr = pd.concat([
        h - l,
        (h - c.shift(1)).abs(),
        (l - c.shift(1)).abs(),
    ], axis=1).max(axis=1)
    df["atr_14"] = tr.rolling(14).mean()
    df["atr_norm"] = df["atr_14"] / c

    df["vol_ma_20"] = v.rolling(20).mean()
    df["vol_ratio"] = v / df["vol_ma_20"].replace(0, 1e-9)

    for lag in [1, 2, 3, 5]:
        df[f"ret_lag_{lag}"] = df["returns"].shift(lag)

    df["mom_5"] = c / c.shift(5) - 1
    df["mom_10"] = c / c.shift(10) - 1
    df["mom_20"] = c / c.shift(20) - 1

    df["high_low_range"] = (h - l) / c
    df["close_position"] = (c - l) / (h - l).replace(0, 1e-9)

    df["rolling_vol_5"] = df["returns"].rolling(5).std()
    df["rolling_vol_20"] = df["returns"].rolling(20).std()

    return df


def add_labels(df, forward_bars=FORWARD_BARS, buy_thresh=BUY_THRESH, sell_thresh=SELL_THRESH):
    future_return = df["close"].shift(-forward_bars) / df["close"] - 1
    df["forward_return"] = future_return
    df["label"] = 1  # HOLD
    df.loc[future_return > buy_thresh, "label"] = 2   # BUY
    df.loc[future_return < sell_thresh, "label"] = 0   # SELL
    return df


def build_dataset():
    client = get_client()
    all_dfs = []

    for symbol in SYMBOLS:
        print(f"Fetching {symbol}...")
        df_1h = fetch_klines(client, symbol, "60", 1000)
        if df_1h.empty:
            print(f"  skipped {symbol} (no data)")
            continue

        df_1h = engineer_features(df_1h)
        df_1h = add_labels(df_1h)
        df_1h["symbol"] = symbol
        df_1h = df_1h.dropna()
        all_dfs.append(df_1h)
        print(f"  {symbol}: {len(df_1h)} samples")

    dataset = pd.concat(all_dfs, ignore_index=True)
    print(f"\nTotal: {len(dataset)} samples")
    print(f"Label distribution:\n{dataset['label'].value_counts().sort_index()}")
    return dataset


FEATURE_COLS = [
    "returns", "log_returns",
    "ema_ratio_8", "ema_ratio_21", "ema_ratio_50", "ema_cross_8_21",
    "rsi_14", "rsi_7",
    "macd", "macd_signal", "macd_hist",
    "bb_pct",
    "atr_norm",
    "vol_ratio",
    "ret_lag_1", "ret_lag_2", "ret_lag_3", "ret_lag_5",
    "mom_5", "mom_10", "mom_20",
    "high_low_range", "close_position",
    "rolling_vol_5", "rolling_vol_20",
]


if __name__ == "__main__":
    dataset = build_dataset()
    out = os.path.join(os.path.dirname(__file__), "dataset.csv")
    dataset.to_csv(out, index=False)
    print(f"Saved to {out}")
