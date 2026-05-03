"""
Enhanced data collection with:
- 5,000 1h candles per symbol (7 months)
- Funding rate (8h intervals, forward-filled to 1h)
- Open interest (1h)
- Long/short ratio (1h)
- Triple barrier labeling
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
    "AVAXUSDT", "ARBUSDT", "WIFUSDT", "1000PEPEUSDT",
    "BNBUSDT", "MATICUSDT", "OPUSDT", "APTUSDT",
    "INJUSDT", "TIAUSDT", "SEIUSDT", "NEARUSDT",
]

KLINE_LIMIT = 5000
ATR_MULT_UPPER = 1.5   # +1.5 ATR = BUY barrier
ATR_MULT_LOWER = 1.0   # -1.0 ATR = SELL barrier
MAX_HOLD_BARS  = 12    # max 12h holding period


def get_client():
    c = HTTP()
    if settings.bybit_proxy:
        c.client.proxies = {"http": settings.bybit_proxy, "https": settings.bybit_proxy}
    return c


def fetch_klines(client, symbol, interval="60", limit=5000):
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
        time.sleep(0.05)

    seen, candles = set(), []
    for r in reversed(all_rows):
        ts = int(r[0])
        if ts in seen:
            continue
        seen.add(ts)
        candles.append({"timestamp": ts, "open": float(r[1]), "high": float(r[2]),
                        "low": float(r[3]), "close": float(r[4]), "volume": float(r[5])})
    return pd.DataFrame(candles)


def fetch_funding_rate(client, symbol, limit=1000):
    all_rows = []
    end_time = None
    while len(all_rows) < limit:
        params = {"category": "linear", "symbol": symbol, "limit": 200}
        if end_time:
            params["endTime"] = end_time
        resp = client.get_funding_rate_history(**params)
        if resp["retCode"] != 0:
            break
        rows = resp["result"]["list"]
        if not rows:
            break
        all_rows.extend(rows)
        end_time = int(rows[-1]["fundingRateTimestamp"]) - 1
        if len(rows) < 200:
            break
        time.sleep(0.05)

    records = [{"timestamp": int(r["fundingRateTimestamp"]),
                "funding_rate": float(r["fundingRate"])} for r in reversed(all_rows)]
    return pd.DataFrame(records) if records else pd.DataFrame(columns=["timestamp", "funding_rate"])


def fetch_open_interest(client, symbol, limit=1000):
    all_rows = []
    end_time = None
    while len(all_rows) < limit:
        params = {"category": "linear", "symbol": symbol, "intervalTime": "1h", "limit": 200}
        if end_time:
            params["endTime"] = end_time
        resp = client.get_open_interest(**params)
        if resp["retCode"] != 0:
            break
        rows = resp["result"]["list"]
        if not rows:
            break
        all_rows.extend(rows)
        end_time = int(rows[-1]["timestamp"]) - 1
        if len(rows) < 200:
            break
        time.sleep(0.05)

    records = [{"timestamp": int(r["timestamp"]),
                "open_interest": float(r["openInterest"])} for r in reversed(all_rows)]
    return pd.DataFrame(records) if records else pd.DataFrame(columns=["timestamp", "open_interest"])


def fetch_long_short(client, symbol, limit=500):
    resp = client.get_long_short_ratio(category="linear", symbol=symbol, period="1h", limit=limit)
    if resp["retCode"] != 0 or not resp["result"]["list"]:
        return pd.DataFrame(columns=["timestamp", "long_short_ratio"])
    rows = resp["result"]["list"]
    records = [{"timestamp": int(r["timestamp"]),
                "long_short_ratio": float(r["buyRatio"]) / max(float(r["sellRatio"]), 1e-9)}
               for r in reversed(rows)]
    return pd.DataFrame(records)


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

    df["returns"]     = c.pct_change()
    df["log_returns"] = np.log(c / c.shift(1))

    for p in [8, 21, 50]:
        df[f"ema_{p}"]       = ema(c, p)
        df[f"ema_ratio_{p}"] = c / df[f"ema_{p}"]
    df["ema_cross_8_21"] = df["ema_8"] - df["ema_21"]

    df["rsi_14"] = rsi(c, 14)
    df["rsi_7"]  = rsi(c, 7)

    ema12 = ema(c, 12); ema26 = ema(c, 26)
    df["macd"]        = ema12 - ema26
    df["macd_signal"] = ema(df["macd"], 9)
    df["macd_hist"]   = df["macd"] - df["macd_signal"]

    bb_mid = c.rolling(20).mean()
    bb_std = c.rolling(20).std()
    df["bb_pct"] = (c - (bb_mid - 2*bb_std)) / ((4*bb_std).replace(0, 1e-9))

    tr = pd.concat([h-l, (h-c.shift(1)).abs(), (l-c.shift(1)).abs()], axis=1).max(axis=1)
    df["atr_14"]  = tr.rolling(14).mean()
    df["atr_norm"] = df["atr_14"] / c

    df["vol_ma_20"] = v.rolling(20).mean()
    df["vol_ratio"] = v / df["vol_ma_20"].replace(0, 1e-9)

    for lag in [1, 2, 3, 5]:
        df[f"ret_lag_{lag}"] = df["returns"].shift(lag)

    for m in [5, 10, 20]:
        df[f"mom_{m}"] = c / c.shift(m) - 1

    df["high_low_range"] = (h - l) / c
    df["close_position"] = (c - l) / (h - l).replace(0, 1e-9)
    df["rolling_vol_5"]  = df["returns"].rolling(5).std()
    df["rolling_vol_20"] = df["returns"].rolling(20).std()

    # Funding rate features
    if "funding_rate" in df.columns:
        df["funding_rate_ma8"]  = df["funding_rate"].rolling(8).mean()
        df["funding_rate_std8"] = df["funding_rate"].rolling(8).std()
        df["funding_cumulative"] = df["funding_rate"].rolling(24).sum()
    else:
        df["funding_rate"]       = 0.0
        df["funding_rate_ma8"]   = 0.0
        df["funding_rate_std8"]  = 0.0
        df["funding_cumulative"] = 0.0

    # Open interest features
    if "open_interest" in df.columns:
        df["oi_change"]    = df["open_interest"].pct_change()
        df["oi_ma8"]       = df["open_interest"].rolling(8).mean()
        df["oi_ratio"]     = df["open_interest"] / df["oi_ma8"].replace(0, 1e-9)
        df["oi_price_div"] = df["oi_change"] - df["returns"]  # OI vs price divergence
    else:
        df["oi_change"]    = 0.0
        df["oi_ratio"]     = 1.0
        df["oi_price_div"] = 0.0

    # Long/short ratio features
    if "long_short_ratio" in df.columns:
        df["ls_ma8"]   = df["long_short_ratio"].rolling(8).mean()
        df["ls_change"] = df["long_short_ratio"].pct_change()
    else:
        df["long_short_ratio"] = 1.0
        df["ls_ma8"]           = 1.0
        df["ls_change"]        = 0.0

    return df


def triple_barrier_label(df, atr_col="atr_14", upper_mult=ATR_MULT_UPPER,
                          lower_mult=ATR_MULT_LOWER, max_bars=MAX_HOLD_BARS):
    """
    For each bar, the label is determined by which barrier is hit first:
    - Upper (+upper_mult * ATR): BUY (2)
    - Lower (-lower_mult * ATR): SELL (0)
    - Time (max_bars): return direction (1 if positive, else 0)
    - Default HOLD (1) if no barrier hit
    """
    closes = df["close"].values
    atrs   = df[atr_col].values
    n      = len(closes)
    labels = np.ones(n, dtype=np.int64)

    for i in range(n - 1):
        if np.isnan(atrs[i]) or atrs[i] == 0:
            continue
        upper = closes[i] + upper_mult * atrs[i]
        lower = closes[i] - lower_mult * atrs[i]
        horizon = min(i + max_bars, n - 1)

        hit = 1  # HOLD default
        for j in range(i + 1, horizon + 1):
            if closes[j] >= upper:
                hit = 2  # BUY
                break
            elif closes[j] <= lower:
                hit = 0  # SELL
                break
        else:
            # Time barrier: label by direction
            fwd = closes[horizon] / closes[i] - 1
            hit = 2 if fwd > 0.003 else (0 if fwd < -0.003 else 1)

        labels[i] = hit

    df["label"] = labels
    return df


FEATURE_COLS = [
    "returns", "log_returns",
    "ema_ratio_8", "ema_ratio_21", "ema_ratio_50", "ema_cross_8_21",
    "rsi_14", "rsi_7",
    "macd", "macd_signal", "macd_hist",
    "bb_pct", "atr_norm",
    "vol_ratio",
    "ret_lag_1", "ret_lag_2", "ret_lag_3", "ret_lag_5",
    "mom_5", "mom_10", "mom_20",
    "high_low_range", "close_position",
    "rolling_vol_5", "rolling_vol_20",
    # New features
    "funding_rate", "funding_rate_ma8", "funding_rate_std8", "funding_cumulative",
    "oi_change", "oi_ratio", "oi_price_div",
    "long_short_ratio", "ls_ma8", "ls_change",
]


def build_dataset():
    client = get_client()
    all_dfs = []

    for symbol in SYMBOLS:
        print(f"Fetching {symbol}...")
        try:
            df = fetch_klines(client, symbol, "60", KLINE_LIMIT)
            if df.empty or len(df) < 200:
                print(f"  skipped (insufficient klines: {len(df)})")
                continue
            print(f"  klines: {len(df)}")

            # Funding rate — 8h timestamps, forward-fill to 1h
            fr_df = fetch_funding_rate(client, symbol, 1000)
            if not fr_df.empty:
                fr_df = fr_df.set_index("timestamp").reindex(df["timestamp"]).ffill()
                df["funding_rate"] = fr_df["funding_rate"].values
            time.sleep(0.1)

            # Open interest — 1h timestamps, merge
            oi_df = fetch_open_interest(client, symbol, 1000)
            if not oi_df.empty:
                oi_df = oi_df.set_index("timestamp").reindex(df["timestamp"]).ffill()
                df["open_interest"] = oi_df["open_interest"].values
            time.sleep(0.1)

            # Long/short ratio
            ls_df = fetch_long_short(client, symbol, 500)
            if not ls_df.empty:
                ls_df = ls_df.set_index("timestamp").reindex(df["timestamp"]).ffill()
                df["long_short_ratio"] = ls_df["long_short_ratio"].values
            time.sleep(0.1)

            df = engineer_features(df)
            df = triple_barrier_label(df)
            df["symbol"] = symbol
            df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=FEATURE_COLS + ["label"])
            all_dfs.append(df)
            print(f"  {symbol}: {len(df)} samples, label dist: {dict(df['label'].value_counts().sort_index())}")

        except Exception as e:
            print(f"  ERROR {symbol}: {e}")
            continue

    dataset = pd.concat(all_dfs, ignore_index=True)
    print(f"\nTotal: {len(dataset)} samples across {len(all_dfs)} symbols")
    print(f"Label distribution:\n{dataset['label'].value_counts().sort_index()}")
    return dataset


if __name__ == "__main__":
    dataset = build_dataset()
    out = os.path.join(os.path.dirname(__file__), "dataset.csv")
    dataset[FEATURE_COLS + ["label", "symbol", "timestamp"]].to_csv(out, index=False)
    print(f"Saved to {out}")
