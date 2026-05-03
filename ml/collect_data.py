"""
Enhanced data collection — Phase 1 improvements:

- Recency filter: last 18 months only (recent market structure generalises better)
- Taker buy/sell ratio feature (from Binance kline col 9/10)
- Symmetric triple barrier: 2.0×ATR up AND down (removes label asymmetry)
- Longer horizon: 24 bars (1 day)
- All existing: funding rates, OI, L/S ratio, 35 base features
"""

import sys
import os
import time
import numpy as np
import pandas as pd
import requests
from pybit.unified_trading import HTTP

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from api.config import settings

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "SUIUSDT",
    "DOGEUSDT", "XRPUSDT", "LINKUSDT", "AAVEUSDT",
    "AVAXUSDT", "ARBUSDT", "WIFUSDT", "1000PEPEUSDT",
    "BNBUSDT", "OPUSDT", "APTUSDT",
    "INJUSDT", "TIAUSDT", "SEIUSDT", "NEARUSDT",
]

# Binance uses same symbol names except 1000PEPE
BINANCE_SYMBOL_MAP = {"1000PEPEUSDT": "1000PEPEUSDT"}

BINANCE_URL = "https://fapi.binance.com/fapi/v1/klines"
BINANCE_FUNDING_URL = "https://fapi.binance.com/fapi/v1/fundingRate"
import datetime

# Recency filter: only keep last 18 months
RECENCY_MONTHS = 18
RECENCY_START_MS = int((datetime.datetime.utcnow() - datetime.timedelta(days=RECENCY_MONTHS * 30)).timestamp() * 1000)

MAX_CANDLES = 15000  # enough for 18 months of 1h bars (~13,140)
# Symmetric barriers + longer horizon
ATR_MULT_UPPER = 2.0
ATR_MULT_LOWER = 2.0
MAX_HOLD_BARS  = 24


def get_proxies():
    if settings.bybit_proxy:
        return {"http": settings.bybit_proxy, "https": settings.bybit_proxy}
    return None


def get_bybit_client():
    c = HTTP()
    if settings.bybit_proxy:
        c.client.proxies = {"http": settings.bybit_proxy, "https": settings.bybit_proxy}
    return c


def fetch_binance_klines(symbol, interval="1h", limit=MAX_CANDLES, start_ms=RECENCY_START_MS):
    """Paginate Binance futures klines from start_ms to now, oldest first.

    Binance kline columns:
    0:open_time 1:open 2:high 3:low 4:close 5:volume 6:close_time
    7:quote_volume 8:trades 9:taker_buy_base_vol 10:taker_buy_quote_vol
    """
    proxies = get_proxies()
    bsym = BINANCE_SYMBOL_MAP.get(symbol, symbol)
    all_candles = []
    current_start = start_ms

    while len(all_candles) < limit:
        batch = min(1500, limit - len(all_candles))
        params = {"symbol": bsym, "interval": interval, "limit": batch, "startTime": current_start}

        r = requests.get(BINANCE_URL, params=params, proxies=proxies, timeout=30)
        if r.status_code != 200:
            print(f"    Binance error {r.status_code}: {r.text[:200]}")
            break

        data = r.json()
        if not data:
            break

        all_candles.extend(data)
        current_start = data[-1][0] + 1  # next batch starts after last candle
        if len(data) < batch:
            break
        time.sleep(0.1)

    seen = set()
    result = []
    for row in all_candles:
        ts = row[0]
        if ts in seen:
            continue
        seen.add(ts)
        vol = float(row[5])
        taker_buy_vol = float(row[9]) if len(row) > 9 else 0.0
        # taker buy ratio: proportion of volume initiated by buyers
        taker_buy_ratio = taker_buy_vol / vol if vol > 0 else 0.5
        result.append({
            "timestamp": ts,
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": vol,
            "taker_buy_ratio": taker_buy_ratio,
        })
    result.sort(key=lambda x: x["timestamp"])
    return pd.DataFrame(result)


def fetch_binance_funding(symbol, limit=5000):
    """Fetch funding rate history from Binance, oldest first."""
    proxies = get_proxies()
    bsym = BINANCE_SYMBOL_MAP.get(symbol, symbol)
    all_rows = []
    start_time = None

    while len(all_rows) < limit:
        params = {"symbol": bsym, "limit": 1000}
        if start_time:
            params["startTime"] = start_time

        r = requests.get(BINANCE_FUNDING_URL, params=params, proxies=proxies, timeout=30)
        if r.status_code != 200:
            break

        data = r.json()
        if not data:
            break

        all_rows.extend(data)
        start_time = data[-1]["fundingTime"] + 1
        if len(data) < 1000:
            break
        time.sleep(0.15)

    records = [{"timestamp": int(r["fundingTime"]),
                "funding_rate": float(r["fundingRate"])} for r in all_rows]
    return pd.DataFrame(records) if records else pd.DataFrame(columns=["timestamp", "funding_rate"])


def fetch_bybit_oi(client, symbol, limit=1000):
    all_rows = []
    end_time = None
    while len(all_rows) < limit:
        params = {"category": "linear", "symbol": symbol, "intervalTime": "1h", "limit": 200}
        if end_time:
            params["endTime"] = end_time
        try:
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
        except Exception:
            break

    records = [{"timestamp": int(r["timestamp"]),
                "open_interest": float(r["openInterest"])} for r in reversed(all_rows)]
    return pd.DataFrame(records) if records else pd.DataFrame(columns=["timestamp", "open_interest"])


def fetch_bybit_ls(client, symbol, limit=500):
    try:
        resp = client.get_long_short_ratio(category="linear", symbol=symbol, period="1h", limit=limit)
        if resp["retCode"] != 0 or not resp["result"]["list"]:
            return pd.DataFrame(columns=["timestamp", "long_short_ratio"])
        rows = resp["result"]["list"]
        records = [{"timestamp": int(r["timestamp"]),
                    "long_short_ratio": float(r["buyRatio"]) / max(float(r["sellRatio"]), 1e-9)}
                   for r in reversed(rows)]
        return pd.DataFrame(records)
    except Exception:
        return pd.DataFrame(columns=["timestamp", "long_short_ratio"])


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

    # Taker buy ratio features (buyer aggression)
    if "taker_buy_ratio" in df.columns:
        df["taker_buy_ratio"]    = df["taker_buy_ratio"].fillna(0.5)
        df["taker_buy_ma8"]      = df["taker_buy_ratio"].rolling(8, min_periods=1).mean()
        df["taker_buy_delta"]    = df["taker_buy_ratio"] - df["taker_buy_ma8"]
        df["taker_buy_pressure"] = (df["taker_buy_ratio"] - 0.5) * df["vol_ratio"]
    else:
        df["taker_buy_ratio"]    = 0.5
        df["taker_buy_ma8"]      = 0.5
        df["taker_buy_delta"]    = 0.0
        df["taker_buy_pressure"] = 0.0

    # Funding rate features (ffill 8h values to 1h, fill remaining NaN with 0)
    if "funding_rate" in df.columns:
        df["funding_rate"]       = df["funding_rate"].ffill().fillna(0.0)
        df["funding_rate_ma8"]   = df["funding_rate"].rolling(8, min_periods=1).mean()
        df["funding_rate_std8"]  = df["funding_rate"].rolling(8, min_periods=1).std().fillna(0.0)
        df["funding_cumulative"] = df["funding_rate"].rolling(24, min_periods=1).sum()
    else:
        df["funding_rate"]       = 0.0
        df["funding_rate_ma8"]   = 0.0
        df["funding_rate_std8"]  = 0.0
        df["funding_cumulative"] = 0.0

    # Open interest features (fill missing with neutral values for historical rows)
    if "open_interest" in df.columns:
        # Forward-fill from last known value, then fill remaining NaN with 0
        df["open_interest"] = df["open_interest"].ffill().fillna(0.0)
        df["oi_change"]     = df["open_interest"].pct_change().fillna(0.0)
        df["oi_ma8"]        = df["open_interest"].rolling(8, min_periods=1).mean()
        df["oi_ratio"]      = (df["open_interest"] / df["oi_ma8"].replace(0, 1e-9)).fillna(1.0)
        df["oi_price_div"]  = (df["oi_change"] - df["returns"]).fillna(0.0)
    else:
        df["oi_change"]    = 0.0
        df["oi_ratio"]     = 1.0
        df["oi_price_div"] = 0.0

    # Long/short ratio features (fill missing with neutral 1.0)
    if "long_short_ratio" in df.columns:
        df["long_short_ratio"] = df["long_short_ratio"].ffill().fillna(1.0)
        df["ls_ma8"]           = df["long_short_ratio"].rolling(8, min_periods=1).mean()
        df["ls_change"]        = df["long_short_ratio"].pct_change().fillna(0.0)
    else:
        df["long_short_ratio"] = 1.0
        df["ls_ma8"]           = 1.0
        df["ls_change"]        = 0.0

    return df


def triple_barrier_label(df, atr_col="atr_14", upper_mult=ATR_MULT_UPPER,
                          lower_mult=ATR_MULT_LOWER, max_bars=MAX_HOLD_BARS):
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

        hit = 1
        for j in range(i + 1, horizon + 1):
            if closes[j] >= upper:
                hit = 2
                break
            elif closes[j] <= lower:
                hit = 0
                break
        else:
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
    # Taker buy/sell pressure (new)
    "taker_buy_ratio", "taker_buy_ma8", "taker_buy_delta", "taker_buy_pressure",
    # Market microstructure
    "funding_rate", "funding_rate_ma8", "funding_rate_std8", "funding_cumulative",
    "oi_change", "oi_ratio", "oi_price_div",
    "long_short_ratio", "ls_ma8", "ls_change",
]


def build_dataset():
    bybit_client = get_bybit_client()
    all_dfs = []

    for symbol in SYMBOLS:
        print(f"\n{'='*50}")
        print(f"Fetching {symbol}...")
        try:
            # 1. Binance klines (main data source — years of history)
            df = fetch_binance_klines(symbol, "1h", MAX_CANDLES)
            if df.empty or len(df) < 200:
                print(f"  skipped (insufficient klines: {len(df)})")
                continue
            print(f"  Binance klines: {len(df)} ({len(df)//24} days)")

            # 2. Binance funding rates — merge into klines
            fr_df = fetch_binance_funding(symbol, 10000)
            if not fr_df.empty:
                fr_df = fr_df.set_index("timestamp").reindex(df["timestamp"]).ffill().bfill()
                df["funding_rate"] = fr_df["funding_rate"].values
                print(f"  Binance funding: {len(fr_df)} records")

            # 3. Bybit OI (recent only — fill NaN with 0 for historical rows)
            oi_df = fetch_bybit_oi(bybit_client, symbol, 1000)
            if not oi_df.empty:
                oi_indexed = oi_df.set_index("timestamp").reindex(df["timestamp"]).ffill()
                df["open_interest"] = oi_indexed["open_interest"].values
                print(f"  Bybit OI: {len(oi_df)} records")
            time.sleep(0.1)

            # 4. Bybit L/S ratio (recent only — fill NaN with 1.0 for historical rows)
            ls_df = fetch_bybit_ls(bybit_client, symbol, 500)
            if not ls_df.empty:
                ls_indexed = ls_df.set_index("timestamp").reindex(df["timestamp"]).ffill()
                df["long_short_ratio"] = ls_indexed["long_short_ratio"].values
                print(f"  Bybit L/S: {len(ls_df)} records")
            time.sleep(0.1)

            # 5. Engineer features + labels
            df = engineer_features(df)
            df = triple_barrier_label(df)
            df["symbol"] = symbol
            df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=FEATURE_COLS + ["label"])
            all_dfs.append(df)
            dist = dict(df["label"].value_counts().sort_index())
            print(f"  Final: {len(df)} samples, labels: {dist}")

        except Exception as e:
            print(f"  ERROR {symbol}: {e}")
            continue

    dataset = pd.concat(all_dfs, ignore_index=True)
    print(f"\n{'='*50}")
    print(f"Total: {len(dataset)} samples across {len(all_dfs)} symbols")
    print(f"Label distribution:\n{dataset['label'].value_counts().sort_index()}")
    return dataset


if __name__ == "__main__":
    dataset = build_dataset()
    out = os.path.join(os.path.dirname(__file__), "dataset.csv")
    dataset[FEATURE_COLS + ["label", "symbol", "timestamp"]].to_csv(out, index=False)
    print(f"\nSaved to {out}")
