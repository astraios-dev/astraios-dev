"""
Data collection v5 — multi-timeframe:

- 3 timeframes per symbol: 15m (momentum), 1h (trend), 4h (regime)
- Each timeframe gets the same 28-feature set, prefixed m15_ / h1_ / h4_
- Features aligned to 1h master timestamps via forward-fill
- Total: 84 features per row (28 × 3 timeframes)
- Return-quantile labels on 1h bars (24-bar forward return, top/bottom 30%)
- Quality gate: skip symbols with >50% zero returns
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
    # Majors — 3-year history available
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    # Large alts
    "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "AAVEUSDT", "UNIUSDT",
    # Mid alts
    "SUIUSDT", "ARBUSDT", "OPUSDT", "APTUSDT", "NEARUSDT",
    "INJUSDT", "TIAUSDT", "SEIUSDT",
    # Meme / high-vol
    "WIFUSDT", "1000PEPEUSDT", "BONKUSDT",
    # Additional liquid perps
    "LDOUSDT", "ATOMUSDT", "DOTUSDT",
    "ADAUSDT", "MATICUSDT", "LTCUSDT", "TRXUSDT",
    # FTMUSDT excluded — delisting caused 75% zero-return bars, label artefact
]

# Minimum fraction of non-zero returns required — filters illiquid/delisted assets
MIN_NONZERO_RETURN_FRAC = 0.30

# Symbols with 3-year history on Binance futures
LONG_HISTORY_SYMBOLS = {"BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
                         "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "ADAUSDT", "MATICUSDT",
                         "LTCUSDT", "DOTUSDT", "ATOMUSDT", "TRXUSDT"}

# Binance uses same symbol names except 1000PEPE
BINANCE_SYMBOL_MAP = {"1000PEPEUSDT": "1000PEPEUSDT"}

BINANCE_URL = "https://fapi.binance.com/fapi/v1/klines"
BINANCE_FUNDING_URL = "https://fapi.binance.com/fapi/v1/fundingRate"
import datetime

MAX_CANDLES_SHORT = 15000   # 18 months at 1h
MAX_CANDLES_LONG  = 30000   # 3+ years at 1h (~26,280)
RECENCY_MONTHS_SHORT = 18
RECENCY_MONTHS_LONG  = 36

def _start_ms(months):
    return int((datetime.datetime.utcnow() - datetime.timedelta(days=months * 30)).timestamp() * 1000)


def get_proxies():
    if settings.bybit_proxy:
        return {"http": settings.bybit_proxy, "https": settings.bybit_proxy}
    return None


def get_bybit_client():
    c = HTTP()
    if settings.bybit_proxy:
        c.client.proxies = {"http": settings.bybit_proxy, "https": settings.bybit_proxy}
    return c


def fetch_binance_klines(symbol, interval="1h", limit=MAX_CANDLES_SHORT, start_ms=None):
    """Paginate Binance futures klines from start_ms to now, oldest first.

    Binance kline columns:
    0:open_time 1:open 2:high 3:low 4:close 5:volume 6:close_time
    7:quote_volume 8:trades 9:taker_buy_base_vol 10:taker_buy_quote_vol
    """
    proxies = get_proxies()
    bsym = BINANCE_SYMBOL_MAP.get(symbol, symbol)
    all_candles = []
    current_start = start_ms if start_ms is not None else _start_ms(RECENCY_MONTHS_SHORT)

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

    # --- Regime features ---
    ret = df["returns"].fillna(0)

    # vol_regime: ratio of short-term to long-term realised vol
    # >1 = elevated/expanding vol, <1 = calm/contracting vol
    rv5  = ret.rolling(5).std().fillna(0)
    rv20 = ret.rolling(20).std().fillna(1e-9)
    df["vol_regime"] = (rv5 / rv20.replace(0, 1e-9)).fillna(1.0).clip(0, 5)

    # trend_strength: ADX-proxy using EMA slope normalised by ATR
    ema50_slope = (df["ema_50"].diff(5) / df["atr_14"].replace(0, 1e-9)).fillna(0)
    df["trend_strength"] = ema50_slope.clip(-5, 5)

    # price_vs_sma200: position of close relative to 200-bar SMA (regime anchor)
    sma200 = c.rolling(200, min_periods=50).mean()
    df["price_vs_sma200"] = ((c - sma200) / sma200.replace(0, 1e-9)).fillna(0).clip(-1, 1)

    return df


def engineer_features_tf(df, prefix):
    """Engineer features for a non-primary timeframe and return as a prefixed Series dict.

    Returns a dict {prefixed_col: np.array} aligned to df.index.
    """
    feats = {}
    df = df.copy()
    engineer_features(df)  # adds columns in-place

    for col in BASE_FEATURE_COLS:
        if col in df.columns:
            feats[f"{prefix}_{col}"] = df[col].values
        else:
            feats[f"{prefix}_{col}"] = np.zeros(len(df))
    return feats


def quantile_label(df, horizon=24, buy_quantile=0.70, sell_quantile=0.30):
    """Per-symbol return-quantile labels.

    Forward return over `horizon` bars is computed for each row. Rows whose
    forward return is in the top (1-buy_quantile) of the symbol's distribution
    are labelled BUY=1; bottom sell_quantile are labelled SELL=0. The middle
    40% are dropped — they are too noisy to learn from.

    This is symbol-relative and adapts to volatility regimes automatically.
    """
    closes = df["close"].values
    n = len(closes)
    fwd_returns = np.full(n, np.nan)

    for i in range(n - horizon):
        fwd_returns[i] = closes[i + horizon] / closes[i] - 1

    df["fwd_return"] = fwd_returns

    # Compute quantile thresholds on non-nan rows only
    valid = fwd_returns[~np.isnan(fwd_returns)]
    q_buy  = np.quantile(valid, buy_quantile)
    q_sell = np.quantile(valid, sell_quantile)

    labels = np.full(n, -1, dtype=np.int64)
    for i in range(n):
        if np.isnan(fwd_returns[i]):
            continue
        if fwd_returns[i] >= q_buy:
            labels[i] = 1   # BUY
        elif fwd_returns[i] <= q_sell:
            labels[i] = 0   # SELL
        # middle band → stays -1 (dropped)

    df["label"] = labels
    df = df[df["label"] >= 0].copy()
    df = df.drop(columns=["fwd_return"])
    return df


# Per-timeframe features (28) — same set applied at 15m, 1h, 4h
BASE_FEATURE_COLS = [
    # Price action (5)
    "returns",
    "ema_ratio_8", "ema_ratio_21", "ema_ratio_50",
    "close_position",
    # Momentum (4)
    "rsi_14",
    "macd_hist",
    "bb_pct",
    "mom_20",
    # Volatility (3)
    "atr_norm",
    "rolling_vol_5", "rolling_vol_20",
    # Volume (3)
    "vol_ratio",
    "taker_buy_ratio", "taker_buy_pressure",
    # Lagged returns (2)
    "ret_lag_1", "ret_lag_3",
    # Microstructure — funding only (2)
    "funding_rate", "funding_rate_ma8",
    # Cross-asset context (4)
    "btc_returns", "btc_mom_5",
    "btc_vol_ratio", "btc_trend",
    # Regime features (3)
    "vol_regime", "trend_strength", "price_vs_sma200",
    # Correlation + funding divergence (2)
    "btc_corr_20", "funding_divergence",
]

# Multi-timeframe feature columns: 1h (primary) · 15m (momentum) · 4h (regime)
# Total: 28 × 3 = 84 features per row
FEATURE_COLS = (
    [f"h1_{c}" for c in BASE_FEATURE_COLS] +
    [f"m15_{c}" for c in BASE_FEATURE_COLS] +
    [f"h4_{c}" for c in BASE_FEATURE_COLS]
)


def _build_btc_cross_asset(btc_df):
    """Compute BTC cross-asset columns indexed by timestamp (for any timeframe)."""
    c = btc_df["close"]
    ret = c.pct_change().fillna(0)
    ref = pd.DataFrame({"timestamp": btc_df["timestamp"]})
    ref["btc_returns"]   = ret.values
    ref["btc_mom_5"]     = (c / c.shift(5) - 1).fillna(0).values
    ref["btc_vol_ratio"] = (ret.rolling(5).std() / ret.rolling(20).std().replace(0, 1e-9)).fillna(1).clip(0, 5).values
    ema50 = c.ewm(span=50, adjust=False).mean()
    ref["btc_trend"]     = np.sign(c.values - ema50.values).astype(np.float32)
    ref["btc_funding"]   = btc_df["funding_rate"].ffill().fillna(0).values if "funding_rate" in btc_df.columns else 0.0
    return ref.set_index("timestamp")


def _add_btc_cross_asset_to_tf(df_1h, btc_ref_tf, tf_prefix):
    """Align BTC cross-asset features from btc_ref_tf into df_1h, adding prefixed columns."""
    if btc_ref_tf is None:
        for col in ["btc_returns","btc_mom_5","btc_vol_ratio","btc_trend","btc_funding","btc_corr_20","funding_divergence"]:
            df_1h[f"{tf_prefix}_{col}"] = 0.0
        return df_1h

    # Align BTC reference to 1h timestamps
    btc_aligned = btc_ref_tf.reindex(df_1h["timestamp"].values).ffill().fillna(0)
    for col in btc_ref_tf.columns:
        df_1h[f"{tf_prefix}_{col}"] = btc_aligned[col].values

    # Rolling 20-bar correlation vs BTC at this TF (using h1 returns as base)
    sym_ret = pd.Series(df_1h[f"{tf_prefix}_returns"].values if f"{tf_prefix}_returns" in df_1h.columns
                        else df_1h["returns"].values)
    btc_ret = pd.Series(df_1h[f"{tf_prefix}_btc_returns"].values)
    df_1h[f"{tf_prefix}_btc_corr_20"] = sym_ret.rolling(20, min_periods=10).corr(btc_ret).fillna(0)

    # Funding divergence
    fr_sym_col = f"{tf_prefix}_funding_rate"
    fr_sym = df_1h[fr_sym_col].values if fr_sym_col in df_1h.columns else np.zeros(len(df_1h))
    fr_btc = df_1h[f"{tf_prefix}_btc_funding"].values if f"{tf_prefix}_btc_funding" in df_1h.columns else np.zeros(len(df_1h))
    df_1h[f"{tf_prefix}_funding_divergence"] = fr_sym - fr_btc
    return df_1h


_ENGINEERED_COLS = [
    "returns", "ema_ratio_8", "ema_ratio_21", "ema_ratio_50", "close_position",
    "rsi_14", "macd_hist", "bb_pct", "mom_20",
    "atr_norm", "rolling_vol_5", "rolling_vol_20",
    "vol_ratio", "taker_buy_ratio", "taker_buy_pressure",
    "ret_lag_1", "ret_lag_3",
    "funding_rate", "funding_rate_ma8",
    "vol_regime", "trend_strength", "price_vs_sma200",
]
_CROSS_ASSET_COLS = [
    "btc_returns", "btc_mom_5", "btc_vol_ratio", "btc_trend",
    "btc_corr_20", "funding_divergence",
]


def _align_tf_to_1h(df_tf, df_1h_ts, tf_prefix):
    """Engineer features on a secondary TF dataframe and align to 1h timestamps.

    Cross-asset columns (btc_*, btc_corr_20, funding_divergence) are excluded here
    and handled separately by _add_btc_cross_asset_to_tf.
    """
    df_tf = engineer_features(df_tf.copy())
    df_tf_indexed = df_tf.set_index("timestamp")

    # Select only columns that engineer_features actually produces
    avail = [c for c in _ENGINEERED_COLS if c in df_tf_indexed.columns]
    aligned = df_tf_indexed[avail].reindex(df_1h_ts).ffill().fillna(0)

    result = pd.DataFrame(index=range(len(df_1h_ts)))
    for col in BASE_FEATURE_COLS:
        if col in avail:
            result[f"{tf_prefix}_{col}"] = aligned[col].values
        else:
            result[f"{tf_prefix}_{col}"] = 0.0
    return result


def build_dataset():
    all_dfs = []

    # ── Fetch BTC reference at all 3 timeframes ──────────────────────────
    print("Fetching BTC reference data (3 timeframes)...")
    btc_fr_df = fetch_binance_funding("BTCUSDT", 10000)

    btc_refs = {}
    for tf, interval, max_c, months in [
        ("h1",  "1h",  MAX_CANDLES_LONG,   RECENCY_MONTHS_LONG),
        ("m15", "15m", MAX_CANDLES_LONG*4,  RECENCY_MONTHS_LONG),  # 4× more 15m bars
        ("h4",  "4h",  MAX_CANDLES_LONG//4, RECENCY_MONTHS_LONG),
    ]:
        btc_kl = fetch_binance_klines("BTCUSDT", interval, max_c, start_ms=_start_ms(months))
        if not btc_kl.empty:
            if not btc_fr_df.empty:
                fr_idx = btc_fr_df.set_index("timestamp").reindex(btc_kl["timestamp"]).ffill().bfill()
                btc_kl["funding_rate"] = fr_idx["funding_rate"].values
            btc_refs[tf] = _build_btc_cross_asset(btc_kl)
            print(f"  BTC {tf}: {len(btc_kl)} bars")
        else:
            btc_refs[tf] = None

    for symbol in SYMBOLS:
        print(f"\n{'='*50}")
        print(f"Fetching {symbol}...")
        try:
            # ── 1h primary klines ────────────────────────────────────────
            is_long = symbol in LONG_HISTORY_SYMBOLS
            max_candles = MAX_CANDLES_LONG if is_long else MAX_CANDLES_SHORT
            recency_months = RECENCY_MONTHS_LONG if is_long else RECENCY_MONTHS_SHORT
            df_1h = fetch_binance_klines(symbol, "1h", max_candles, start_ms=_start_ms(recency_months))
            if df_1h.empty or len(df_1h) < 200:
                print(f"  skipped (insufficient 1h klines: {len(df_1h)})")
                continue
            nonzero_frac = (df_1h["close"].pct_change().fillna(0) != 0).mean()
            if nonzero_frac < MIN_NONZERO_RETURN_FRAC:
                print(f"  skipped (illiquid: {nonzero_frac:.1%} non-zero returns)")
                continue
            print(f"  1h klines: {len(df_1h)} ({len(df_1h)//24} days, {nonzero_frac:.0%} active)")

            # ── Funding rates → 1h ───────────────────────────────────────
            fr_df = fetch_binance_funding(symbol, 10000)
            if not fr_df.empty:
                fr_idx = fr_df.set_index("timestamp").reindex(df_1h["timestamp"]).ffill().bfill()
                df_1h["funding_rate"] = fr_idx["funding_rate"].values
                print(f"  Funding: {len(fr_df)} records")

            # ── Engineer 1h features + quantile labels ───────────────────
            df_1h = engineer_features(df_1h)
            df_1h = quantile_label(df_1h)
            df_1h_ts = df_1h["timestamp"].values

            # Prefix 1h base features as h1_*
            for col in BASE_FEATURE_COLS:
                df_1h[f"h1_{col}"] = df_1h[col].values if col in df_1h.columns else 0.0

            # Add BTC cross-asset for 1h
            df_1h = _add_btc_cross_asset_to_tf(df_1h, btc_refs.get("h1"), "h1")

            # ── 15m klines → align to 1h ─────────────────────────────────
            df_15m = fetch_binance_klines(symbol, "15m", max_candles * 4, start_ms=_start_ms(recency_months))
            if not df_15m.empty and len(df_15m) >= 60:
                if not fr_df.empty:
                    fr_15m = fr_df.set_index("timestamp").reindex(df_15m["timestamp"]).ffill().bfill()
                    df_15m["funding_rate"] = fr_15m["funding_rate"].values
                tf_feats_15m = _align_tf_to_1h(df_15m, df_1h_ts, "m15")
                for col in tf_feats_15m.columns:
                    df_1h[col] = tf_feats_15m[col].values
                df_1h = _add_btc_cross_asset_to_tf(df_1h, btc_refs.get("m15"), "m15")
                print(f"  15m klines: {len(df_15m)} bars → aligned to {len(df_1h)} 1h rows")
            else:
                for col in [f"m15_{c}" for c in BASE_FEATURE_COLS]:
                    df_1h[col] = 0.0
                for col in ["btc_returns","btc_mom_5","btc_vol_ratio","btc_trend","btc_funding","btc_corr_20","funding_divergence"]:
                    df_1h[f"m15_{col}"] = 0.0

            # ── 4h klines → align to 1h ──────────────────────────────────
            df_4h = fetch_binance_klines(symbol, "4h", max_candles // 4, start_ms=_start_ms(recency_months))
            if not df_4h.empty and len(df_4h) >= 50:
                if not fr_df.empty:
                    fr_4h = fr_df.set_index("timestamp").reindex(df_4h["timestamp"]).ffill().bfill()
                    df_4h["funding_rate"] = fr_4h["funding_rate"].values
                tf_feats_4h = _align_tf_to_1h(df_4h, df_1h_ts, "h4")
                for col in tf_feats_4h.columns:
                    df_1h[col] = tf_feats_4h[col].values
                df_1h = _add_btc_cross_asset_to_tf(df_1h, btc_refs.get("h4"), "h4")
                print(f"  4h klines: {len(df_4h)} bars → aligned to {len(df_1h)} 1h rows")
            else:
                for col in [f"h4_{c}" for c in BASE_FEATURE_COLS]:
                    df_1h[col] = 0.0
                for col in ["btc_returns","btc_mom_5","btc_vol_ratio","btc_trend","btc_funding","btc_corr_20","funding_divergence"]:
                    df_1h[f"h4_{col}"] = 0.0

            df_1h["symbol"] = symbol
            df_1h = df_1h.replace([np.inf, -np.inf], np.nan).dropna(subset=FEATURE_COLS + ["label"])
            all_dfs.append(df_1h)
            dist = dict(df_1h["label"].value_counts().sort_index())
            print(f"  Final: {len(df_1h)} samples, labels: {dist}")

        except Exception as e:
            import traceback
            print(f"  ERROR {symbol}: {e}")
            traceback.print_exc()
            continue

    dataset = pd.concat(all_dfs, ignore_index=True)
    print(f"\n{'='*50}")
    print(f"Total: {len(dataset)} samples across {len(all_dfs)} symbols")
    print(f"Label distribution:\n{dataset['label'].value_counts().sort_index()}")
    return dataset


if __name__ == "__main__":
    dataset = build_dataset()
    out = os.path.join(os.path.dirname(__file__), "dataset.csv")
    # Include close price for TP/SL backtesting in evaluate.py
    save_cols = FEATURE_COLS + ["close", "label", "symbol", "timestamp"]
    save_cols = [c for c in save_cols if c in dataset.columns]
    dataset[save_cols].to_csv(out, index=False)
    print(f"\nSaved to {out}")
