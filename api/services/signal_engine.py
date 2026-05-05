"""
Signal engine powered by trained MarketTransformer.

Falls back to heuristic engine if model files are missing.
"""

import asyncio
import json
import os
from dataclasses import dataclass

import numpy as np

from api.config import settings

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../..", "ml", "output")

SYMBOLS = [
    # Tier 1 — strong model edge (57–59% val acc), auto-trade defaults
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
    "DOGEUSDT", "LTCUSDT", "TRXUSDT", "XRPUSDT",
    # Tier 2 — moderate edge (55–57%), signals shown but not auto-traded by default
    "AVAXUSDT", "LINKUSDT", "ADAUSDT", "DOTUSDT",
    "AAVEUSDT", "SEIUSDT",
    # MATICUSDT excluded — delisted/renamed to POL on Bybit, returns 0 bars
    # Tier 3 — below baseline, signals informational only
    "SUIUSDT", "ARBUSDT", "1000PEPEUSDT", "WIFUSDT",
    "NEARUSDT", "INJUSDT",
    # FTMUSDT excluded — model overfit (100% acc / 0% directional), unreliable
]

_BASE_FEATURES = [
    "returns", "ema_ratio_8", "ema_ratio_21", "ema_ratio_50", "close_position",
    "rsi_14", "macd_hist", "bb_pct", "mom_20",
    "atr_norm", "rolling_vol_5", "rolling_vol_20",
    "vol_ratio", "taker_buy_ratio", "taker_buy_pressure",
    "ret_lag_1", "ret_lag_3",
    "funding_rate", "funding_rate_ma8",
    "btc_returns", "btc_mom_5", "btc_vol_ratio", "btc_trend",
    "vol_regime", "trend_strength", "price_vs_sma200",
    "btc_corr_20", "funding_divergence",
]

# Runtime FEATURE_COLS — overridden from config.json if present (handles v5 single-TF models)
FEATURE_COLS = (
    [f"h1_{c}"  for c in _BASE_FEATURES] +
    [f"m15_{c}" for c in _BASE_FEATURES] +
    [f"h4_{c}"  for c in _BASE_FEATURES]
)

LABEL_MAP_2 = {0: "SELL", 1: "BUY"}
LABEL_MAP_3 = {0: "SELL", 1: "HOLD", 2: "BUY"}

_model = None
_config = None
_scaler_mean = None
_scaler_scale = None


def _load_model():
    global _model, _config, _scaler_mean, _scaler_scale, FEATURE_COLS
    if _model is not None:
        return True

    config_path = os.path.join(MODEL_DIR, "config.json")
    model_path = os.path.join(MODEL_DIR, "model.pt")

    if not os.path.exists(config_path) or not os.path.exists(model_path):
        return False

    try:
        import torch

        with open(config_path) as f:
            _config = json.load(f)

        # Use feature cols from config — handles both v5 (28 single-TF) and v6 (84 MTF)
        if "feature_cols" in _config:
            FEATURE_COLS = _config["feature_cols"]

        _scaler_mean = np.array(_config["scaler"]["mean"], dtype=np.float32)
        _scaler_scale = np.array(_config["scaler"]["scale"], dtype=np.float32)

        from api.services.ml_model import MarketTransformer
        model = MarketTransformer(
            n_features=_config["n_features"],
            d_model=_config["d_model"],
            n_heads=_config["n_heads"],
            n_layers=_config["n_layers"],
            d_ff=_config["d_ff"],
            n_classes=_config["n_classes"],
            dropout=0.0,
            seq_len=_config["seq_len"],
        )
        state = torch.load(model_path, map_location="cpu", weights_only=True)
        model.load_state_dict(state)
        model.eval()
        _model = model
        mtf = _config["n_features"] > 30
        print(f"[signal_engine] Loaded {'MTF 84-feature' if mtf else 'single-TF 28-feature'} model, "
              f"val_acc={_config.get('best_val_acc', 0):.3f}")
        return True
    except Exception as e:
        print(f"[signal_engine] Failed to load model: {e}")
        return False


@dataclass
class SignalResult:
    ticker: str
    action: str
    confidence: float
    rationale: str


def _ema(arr, period):
    alpha = 2 / (period + 1)
    out = np.zeros_like(arr)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def _rsi(closes, period=14):
    delta = np.diff(closes)
    gains = np.where(delta > 0, delta, 0)
    losses = np.where(delta < 0, -delta, 0)
    avg_gain = np.mean(gains[-period:]) if len(gains) >= period else np.mean(gains)
    avg_loss = np.mean(losses[-period:]) if len(losses) >= period else np.mean(losses)
    rs = avg_gain / max(avg_loss, 1e-9)
    return 100 - (100 / (1 + rs))


def _engineer(closes, highs, lows, volumes, taker_buy_ratios=None):
    n = len(closes)
    feats = {}

    ret = np.diff(closes) / closes[:-1]
    feats["returns"] = np.concatenate([[0], ret])
    feats["log_returns"] = np.concatenate([[0], np.log(closes[1:] / closes[:-1])])

    for p in [8, 21, 50]:
        em = _ema(closes, p)
        feats[f"ema_{p}"] = em
        feats[f"ema_ratio_{p}"] = closes / em
    feats["ema_cross_8_21"] = feats["ema_8"] - feats["ema_21"]

    rsi_arr = np.array([_rsi(closes[:i+1]) if i >= 14 else 50.0 for i in range(n)])
    feats["rsi_14"] = rsi_arr
    rsi7_arr = np.array([_rsi(closes[:i+1], 7) if i >= 7 else 50.0 for i in range(n)])
    feats["rsi_7"] = rsi7_arr

    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd = ema12 - ema26
    macd_sig = _ema(macd, 9)
    feats["macd"] = macd
    feats["macd_signal"] = macd_sig
    feats["macd_hist"] = macd - macd_sig

    bb_mid = np.array([np.mean(closes[max(0, i-19):i+1]) for i in range(n)])
    bb_std = np.array([np.std(closes[max(0, i-19):i+1]) for i in range(n)])
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std
    feats["bb_pct"] = (closes - bb_lower) / np.maximum(bb_upper - bb_lower, 1e-9)

    tr = np.maximum(
        highs - lows,
        np.maximum(np.abs(highs - np.concatenate([[closes[0]], closes[:-1]])),
                   np.abs(lows - np.concatenate([[closes[0]], closes[:-1]]))),
    )
    feats["atr_14"] = np.array([np.mean(tr[max(0, i-13):i+1]) for i in range(n)])
    feats["atr_norm"] = feats["atr_14"] / np.maximum(closes, 1e-9)

    vol_ma = np.array([np.mean(volumes[max(0, i-19):i+1]) for i in range(n)])
    feats["vol_ratio"] = volumes / np.maximum(vol_ma, 1e-9)

    for lag in [1, 2, 3, 5]:
        shifted = np.concatenate([np.zeros(lag), feats["returns"][:-lag]])
        feats[f"ret_lag_{lag}"] = shifted

    for m in [5, 10, 20]:
        shifted_c = np.concatenate([np.full(m, closes[0]), closes[:-m]])
        feats[f"mom_{m}"] = closes / np.maximum(shifted_c, 1e-9) - 1

    feats["high_low_range"] = (highs - lows) / np.maximum(closes, 1e-9)
    feats["close_position"] = (closes - lows) / np.maximum(highs - lows, 1e-9)

    feats["rolling_vol_5"] = np.array([np.std(feats["returns"][max(0, i-4):i+1]) for i in range(n)])
    feats["rolling_vol_20"] = np.array([np.std(feats["returns"][max(0, i-19):i+1]) for i in range(n)])

    # Taker buy ratio — from kline data if available, else neutral 0.5
    if taker_buy_ratios is not None and len(taker_buy_ratios) > 0:
        tbr = np.array(taker_buy_ratios, dtype=np.float32)
        tbr_full = np.full(n, 0.5, dtype=np.float32)
        tbr_full[-len(tbr):] = tbr[-n:] if len(tbr) >= n else np.concatenate([np.full(n - len(tbr), 0.5), tbr])
    else:
        tbr_full = np.full(n, 0.5, dtype=np.float32)

    vol_ratio = feats["vol_ratio"]
    tbr_ma8 = np.array([np.mean(tbr_full[max(0, i-7):i+1]) for i in range(n)])
    feats["taker_buy_ratio"]    = tbr_full
    feats["taker_buy_ma8"]      = tbr_ma8
    feats["taker_buy_delta"]    = tbr_full - tbr_ma8
    feats["taker_buy_pressure"] = (tbr_full - 0.5) * vol_ratio

    return feats


def _add_market_microstructure(feats, funding_rates, open_interests, ls_ratios, n):
    """Add funding rate, OI, and long/short ratio features."""

    def _align(arr, n, fill):
        """Align array to exactly n elements by truncating or front-padding."""
        a = np.array(arr, dtype=np.float32)
        if len(a) >= n:
            return a[-n:]
        return np.concatenate([np.full(n - len(a), fill, dtype=np.float32), a])

    # Funding rate (8h, forward-filled)
    if funding_rates is not None and len(funding_rates) > 0:
        fr_full = _align(funding_rates, n, 0.0)
        feats["funding_rate"] = fr_full
        feats["funding_rate_ma8"] = np.array([np.mean(fr_full[max(0, i-7):i+1]) for i in range(n)])
        feats["funding_rate_std8"] = np.array([np.std(fr_full[max(0, i-7):i+1]) + 1e-9 for i in range(n)])
        feats["funding_cumulative"] = np.array([np.sum(fr_full[max(0, i-23):i+1]) for i in range(n)])
    else:
        for k in ["funding_rate", "funding_rate_ma8", "funding_rate_std8", "funding_cumulative"]:
            feats[k] = np.zeros(n, dtype=np.float32)

    # Open interest
    if open_interests is not None and len(open_interests) > 0:
        oi_full = _align(open_interests, n, float(open_interests[0]))
        oi_change = np.concatenate([[0.0], np.diff(oi_full) / np.maximum(oi_full[:-1], 1e-9)])
        oi_ma8 = np.array([np.mean(oi_full[max(0, i-7):i+1]) for i in range(n)])
        feats["oi_change"] = oi_change
        feats["oi_ratio"] = oi_full / np.maximum(oi_ma8, 1e-9)
        feats["oi_price_div"] = oi_change - feats["returns"]
    else:
        feats["oi_change"] = np.zeros(n, dtype=np.float32)
        feats["oi_ratio"] = np.ones(n, dtype=np.float32)
        feats["oi_price_div"] = np.zeros(n, dtype=np.float32)

    # Long/short ratio
    if ls_ratios is not None and len(ls_ratios) > 0:
        ls_full = _align(ls_ratios, n, 1.0)
        feats["long_short_ratio"] = ls_full
        feats["ls_ma8"] = np.array([np.mean(ls_full[max(0, i-7):i+1]) for i in range(n)])
        feats["ls_change"] = np.concatenate([[0.0], np.diff(ls_full) / np.maximum(ls_full[:-1], 1e-9)])
    else:
        feats["long_short_ratio"] = np.ones(n, dtype=np.float32)
        feats["ls_ma8"] = np.ones(n, dtype=np.float32)
        feats["ls_change"] = np.zeros(n, dtype=np.float32)

    return feats


def _feats_to_matrix(feats):
    return np.column_stack([feats[col] for col in FEATURE_COLS]).astype(np.float32)


def _align_arr(arr, n, fill):
    if arr is not None and len(arr) > 0:
        a = np.array(arr, dtype=np.float32)
        if len(a) >= n:
            return a[-n:]
        return np.concatenate([np.full(n - len(a), fill, dtype=np.float32), a])
    return np.full(n, fill, dtype=np.float32)


def _build_tf_feature_vector(closes, highs, lows, volumes, funding_rates,
                              btc_returns, btc_mom_5, btc_vol_ratio, btc_trend, btc_funding,
                              n_1h):
    """Engineer 28 base features for any TF and align (ffill) to n_1h length."""
    n = len(closes)
    feats = _engineer(closes, highs, lows, volumes, None)
    feats = _add_market_microstructure(feats, funding_rates, None, None, n)

    feats["btc_returns"]   = _align_arr(btc_returns, n, 0.0)
    feats["btc_mom_5"]     = _align_arr(btc_mom_5, n, 0.0)
    feats["btc_vol_ratio"] = _align_arr(btc_vol_ratio, n, 1.0)
    feats["btc_trend"]     = _align_arr(btc_trend, n, 0.0)

    ret = feats["returns"]
    rv5  = np.array([np.std(ret[max(0,i-4):i+1])  for i in range(n)], dtype=np.float32)
    rv20 = np.array([np.std(ret[max(0,i-19):i+1]) for i in range(n)], dtype=np.float32)
    feats["vol_regime"] = np.clip(rv5 / np.maximum(rv20, 1e-9), 0, 5)

    ema50 = feats.get("ema_50", np.full(n, closes[-1]))
    atr14 = feats.get("atr_14", np.ones(n))
    slope = np.concatenate([[0.0]*5, (ema50[5:] - ema50[:-5]) / np.maximum(atr14[5:], 1e-9)])
    feats["trend_strength"] = np.clip(slope, -5, 5)

    sma200 = np.array([np.mean(closes[max(0,i-199):i+1]) for i in range(n)], dtype=np.float32)
    feats["price_vs_sma200"] = np.clip((closes - sma200) / np.maximum(sma200, 1e-9), -1, 1)

    btc_ret = _align_arr(btc_returns, n, 0.0)
    corr = np.zeros(n, dtype=np.float32)
    for i in range(20, n):
        s = ret[i-20:i]; b = btc_ret[i-20:i]
        ss, sb = np.std(s), np.std(b)
        if ss > 0 and sb > 0:
            corr[i] = float(np.corrcoef(s, b)[0, 1])
    feats["btc_corr_20"] = corr

    sym_fr = feats.get("funding_rate", np.zeros(n))
    btc_fr = _align_arr(btc_funding, n, 0.0)
    feats["funding_divergence"] = sym_fr - btc_fr

    # Stack into matrix and forward-fill to n_1h length
    mat = np.column_stack([feats.get(c, np.zeros(n)) for c in _BASE_FEATURES]).astype(np.float32)
    mat = np.nan_to_num(mat, nan=0.0, posinf=0.0, neginf=0.0)

    if n == 0 or n_1h == 0:
        return np.zeros((n_1h, len(_BASE_FEATURES)), dtype=np.float32)

    if n >= n_1h:
        # Downsample: take evenly-spaced rows to match 1h length
        idx = np.linspace(0, n - 1, n_1h, dtype=int)
        return mat[idx]
    else:
        # Upsample: ffill by repeating each TF bar to cover 1h resolution
        factor = max(n_1h // n, 1)
        remainder = n_1h - n * factor
        repeated = np.repeat(mat, factor, axis=0)
        if remainder > 0:
            repeated = np.vstack([repeated, np.tile(mat[-1], (remainder, 1))])
        return repeated[:n_1h]


def _predict_symbol(closes, highs, lows, volumes, taker_buy_ratios=None,
                    funding_rates=None, open_interests=None, ls_ratios=None,
                    btc_returns=None, btc_mom_5=None,
                    btc_vol_ratio=None, btc_trend=None, btc_funding=None,
                    seq_len=32,
                    # Secondary TF arrays (MTF model only)
                    closes_15m=None, highs_15m=None, lows_15m=None, volumes_15m=None,
                    funding_15m=None,
                    closes_4h=None, highs_4h=None, lows_4h=None, volumes_4h=None,
                    funding_4h=None,
                    btc_returns_15m=None, btc_trend_15m=None,
                    btc_returns_4h=None, btc_trend_4h=None):
    import torch

    n = len(closes)
    is_mtf = _config is not None and _config.get("n_features", 28) > 30

    # ── 1h features (primary) ────────────────────────────────────────────
    feats_h1 = _engineer(closes, highs, lows, volumes, taker_buy_ratios)
    feats_h1 = _add_market_microstructure(feats_h1, funding_rates, open_interests, ls_ratios, n)

    feats_h1["btc_returns"]   = _align_arr(btc_returns, n, 0.0)
    feats_h1["btc_mom_5"]     = _align_arr(btc_mom_5, n, 0.0)
    feats_h1["btc_vol_ratio"] = _align_arr(btc_vol_ratio, n, 1.0)
    feats_h1["btc_trend"]     = _align_arr(btc_trend, n, 0.0)

    ret = feats_h1["returns"]
    rv5  = np.array([np.std(ret[max(0,i-4):i+1])  for i in range(n)], dtype=np.float32)
    rv20 = np.array([np.std(ret[max(0,i-19):i+1]) for i in range(n)], dtype=np.float32)
    feats_h1["vol_regime"] = np.clip(rv5 / np.maximum(rv20, 1e-9), 0, 5)

    ema50 = feats_h1.get("ema_50", np.full(n, closes[-1]))
    atr14 = feats_h1.get("atr_14", np.ones(n))
    slope = np.concatenate([[0.0]*5, (ema50[5:] - ema50[:-5]) / np.maximum(atr14[5:], 1e-9)])
    feats_h1["trend_strength"] = np.clip(slope, -5, 5)

    sma200 = np.array([np.mean(closes[max(0,i-199):i+1]) for i in range(n)], dtype=np.float32)
    feats_h1["price_vs_sma200"] = np.clip((closes - sma200) / np.maximum(sma200, 1e-9), -1, 1)

    btc_ret = _align_arr(btc_returns, n, 0.0)
    corr = np.zeros(n, dtype=np.float32)
    for i in range(20, n):
        s = ret[i-20:i]; b = btc_ret[i-20:i]
        if np.std(s) > 0 and np.std(b) > 0:
            corr[i] = float(np.corrcoef(s, b)[0, 1])
    feats_h1["btc_corr_20"] = corr

    sym_fr = feats_h1.get("funding_rate", np.zeros(n))
    btc_fr = _align_arr(btc_funding, n, 0.0)
    feats_h1["funding_divergence"] = sym_fr - btc_fr

    mat_h1 = np.column_stack([feats_h1.get(c, np.zeros(n)) for c in _BASE_FEATURES]).astype(np.float32)
    mat_h1 = np.nan_to_num(mat_h1, nan=0.0, posinf=0.0, neginf=0.0)

    if is_mtf:
        # ── 15m features ────────────────────────────────────────────────
        if closes_15m is not None and len(closes_15m) >= 20:
            _n15 = len(closes_15m)
            mat_m15 = _build_tf_feature_vector(
                closes_15m,
                highs_15m    if highs_15m    is not None else closes_15m,
                lows_15m     if lows_15m     is not None else closes_15m,
                volumes_15m  if volumes_15m  is not None else np.ones(_n15, dtype=np.float32),
                funding_15m,
                btc_returns_15m if btc_returns_15m is not None else btc_returns,
                btc_mom_5, btc_vol_ratio,
                btc_trend_15m   if btc_trend_15m   is not None else btc_trend,
                btc_funding, n)
        else:
            mat_m15 = np.zeros((n, len(_BASE_FEATURES)), dtype=np.float32)

        # ── 4h features ─────────────────────────────────────────────────
        if closes_4h is not None and len(closes_4h) >= 10:
            _n4 = len(closes_4h)
            mat_h4 = _build_tf_feature_vector(
                closes_4h,
                highs_4h    if highs_4h    is not None else closes_4h,
                lows_4h     if lows_4h     is not None else closes_4h,
                volumes_4h  if volumes_4h  is not None else np.ones(_n4, dtype=np.float32),
                funding_4h,
                btc_returns_4h if btc_returns_4h is not None else btc_returns,
                btc_mom_5, btc_vol_ratio,
                btc_trend_4h   if btc_trend_4h   is not None else btc_trend,
                btc_funding, n)
        else:
            mat_h4 = np.zeros((n, len(_BASE_FEATURES)), dtype=np.float32)

        feat_matrix = np.hstack([mat_h1, mat_m15, mat_h4])
    else:
        feat_matrix = mat_h1

    feat_matrix = (feat_matrix - _scaler_mean) / np.maximum(_scaler_scale, 1e-9)
    feat_matrix = np.clip(feat_matrix, -5.0, 5.0)

    if len(feat_matrix) < seq_len:
        return None

    seq_input = feat_matrix[-seq_len:]
    x = torch.FloatTensor(seq_input).unsqueeze(0)

    with torch.no_grad():
        logits = _model(x)
        probs = torch.softmax(logits, dim=-1).squeeze().numpy()

    pred_class = int(np.argmax(probs))
    confidence = float(probs[pred_class])

    if _config.get("n_classes") == 2:
        margin = abs(float(probs[1]) - float(probs[0]))
        if margin < 0.10:
            return None

    return pred_class, confidence, probs


def _score_heuristic(closes):
    """Fallback heuristic when model is unavailable."""
    returns = np.diff(closes) / closes[:-1]
    mom_5 = float(np.sum(returns[-5:]))
    mom_20 = float(np.sum(returns)) if len(returns) >= 15 else mom_5
    vol = float(np.std(returns)) if len(returns) > 1 else 0.01
    z_score = (returns[-1] - float(np.mean(returns))) / vol if vol > 0 else 0
    composite = 0.6 * mom_5 + 0.4 * mom_20 - 0.3 * z_score
    if composite > 0.015:
        action, conf = "BUY", round(0.5 + min(abs(composite) / 0.06, 1.0) * 0.45, 2)
    elif composite < -0.015:
        action, conf = "SELL", round(0.5 + min(abs(composite) / 0.06, 1.0) * 0.45, 2)
    else:
        action, conf = "HOLD", round(0.5 + min(abs(composite) / 0.06, 1.0) * 0.45, 2)
    pct_5d = round(mom_5 * 100, 1)
    direction = "up" if pct_5d >= 0 else "down"
    rationale = f"5d momentum {direction} {abs(pct_5d)}%."
    if vol > 0.025:
        rationale += f" Elevated vol ({round(vol * 100, 1)}%)."
    return action, conf, rationale


async def generate_signals(symbols=None):
    from pybit.unified_trading import HTTP

    symbols = symbols or SYMBOLS
    model_ready = _load_model()

    def _run():
        client = HTTP()
        if settings.bybit_proxy:
            client.client.proxies = {"http": settings.bybit_proxy, "https": settings.bybit_proxy}

        # Fetch BTC klines + funding once for cross-asset features
        btc_returns_arr = btc_mom5_arr = btc_vol_ratio_arr = btc_trend_arr = btc_funding_arr = None
        try:
            btc_resp = client.get_kline(category="linear", symbol="BTCUSDT", interval="60", limit=200)
            if btc_resp["retCode"] == 0:
                btc_rows = list(reversed(btc_resp["result"]["list"]))
                btc_closes = np.array([float(r[4]) for r in btc_rows], dtype=np.float32)
                btc_ret = np.concatenate([[0], np.diff(btc_closes) / btc_closes[:-1]])
                btc_returns_arr = btc_ret
                btc_shifted = np.concatenate([np.full(5, btc_closes[0]), btc_closes[:-5]])
                btc_mom5_arr = btc_closes / np.maximum(btc_shifted, 1e-9) - 1
                # vol_ratio: 5-bar / 20-bar realised vol
                rv5  = np.array([np.std(btc_ret[max(0,i-4):i+1]) for i in range(len(btc_ret))])
                rv20 = np.array([np.std(btc_ret[max(0,i-19):i+1]) for i in range(len(btc_ret))])
                btc_vol_ratio_arr = np.clip(rv5 / np.maximum(rv20, 1e-9), 0, 5).astype(np.float32)
                # trend: sign(close - ema50)
                btc_ema50 = btc_closes.copy()
                alpha = 2 / 51
                for i in range(1, len(btc_closes)):
                    btc_ema50[i] = alpha * btc_closes[i] + (1 - alpha) * btc_ema50[i-1]
                btc_trend_arr = np.sign(btc_closes - btc_ema50).astype(np.float32)
        except Exception:
            pass
        # BTC funding rates
        try:
            btc_fr_resp = client.get_funding_rate_history(category="linear", symbol="BTCUSDT", limit=50)
            if btc_fr_resp["retCode"] == 0 and btc_fr_resp["result"]["list"]:
                btc_funding_arr = [float(r["fundingRate"]) for r in reversed(btc_fr_resp["result"]["list"])]
        except Exception:
            pass

        is_mtf = _config is not None and _config.get("n_features", 28) > 30

        results = []
        for sym in symbols:
            try:
                resp = client.get_kline(category="linear", symbol=sym, interval="60", limit=200)
                if resp["retCode"] != 0:
                    continue
                rows = list(reversed(resp["result"]["list"]))
                if len(rows) < 50:
                    continue  # delisted or insufficient data
                closes  = np.array([float(r[4]) for r in rows], dtype=np.float32)
                highs   = np.array([float(r[2]) for r in rows], dtype=np.float32)
                lows    = np.array([float(r[3]) for r in rows], dtype=np.float32)
                volumes = np.array([float(r[5]) for r in rows], dtype=np.float32)
                taker_buy_ratios = None

                # Fetch funding rates (public endpoint)
                funding_rates = None
                try:
                    fr_resp = client.get_funding_rate_history(category="linear", symbol=sym, limit=50)
                    if fr_resp["retCode"] == 0 and fr_resp["result"]["list"]:
                        funding_rates = [float(r["fundingRate"]) for r in reversed(fr_resp["result"]["list"])]
                except Exception:
                    pass

                # MTF: fetch 15m and 4h klines for secondary timeframes
                c15m = h15m = l15m = v15m = None
                c4h  = h4h  = l4h  = v4h  = None
                if is_mtf:
                    try:
                        r15m = client.get_kline(category="linear", symbol=sym, interval="15", limit=800)
                        if r15m["retCode"] == 0:
                            rows15 = list(reversed(r15m["result"]["list"]))
                            c15m = np.array([float(r[4]) for r in rows15], dtype=np.float32)
                            h15m = np.array([float(r[2]) for r in rows15], dtype=np.float32)
                            l15m = np.array([float(r[3]) for r in rows15], dtype=np.float32)
                            v15m = np.array([float(r[5]) for r in rows15], dtype=np.float32)
                    except Exception:
                        pass
                    try:
                        r4h = client.get_kline(category="linear", symbol=sym, interval="240", limit=200)
                        if r4h["retCode"] == 0:
                            rows4 = list(reversed(r4h["result"]["list"]))
                            c4h = np.array([float(r[4]) for r in rows4], dtype=np.float32)
                            h4h = np.array([float(r[2]) for r in rows4], dtype=np.float32)
                            l4h = np.array([float(r[3]) for r in rows4], dtype=np.float32)
                            v4h = np.array([float(r[5]) for r in rows4], dtype=np.float32)
                    except Exception:
                        pass

                if model_ready:
                    result = _predict_symbol(
                        closes, highs, lows, volumes,
                        taker_buy_ratios, funding_rates, None, None,
                        btc_returns_arr, btc_mom5_arr,
                        btc_vol_ratio_arr, btc_trend_arr, btc_funding_arr,
                        _config["seq_len"],
                        closes_15m=c15m, highs_15m=h15m, lows_15m=l15m, volumes_15m=v15m,
                        closes_4h=c4h, highs_4h=h4h, lows_4h=l4h, volumes_4h=v4h,
                    )
                    if result is None:
                        continue
                    pred_class, confidence, probs = result
                    label_map = LABEL_MAP_2 if _config["n_classes"] == 2 else LABEL_MAP_3
                    action = label_map[pred_class]
                    sell_p = float(probs[0])
                    buy_p  = float(probs[1]) if len(probs) > 1 else 1 - sell_p
                    margin = abs(buy_p - sell_p)

                    # ── Build rich structured rationale ──────────────────
                    parts = []

                    # 1. Model conviction
                    if margin >= 0.40:
                        strength = "Strong"
                    elif margin >= 0.25:
                        strength = "Moderate"
                    else:
                        strength = "Weak"
                    parts.append(f"{strength} {action} signal ({confidence:.0%} confidence, {margin:.0%} margin)")

                    # 2. Multi-timeframe confluence
                    tf_clues = []
                    if c15m is not None and len(c15m) >= 4:
                        ret_15m = float(c15m[-1] / c15m[-4] - 1) * 100
                        if (action == "SELL" and ret_15m < -0.3) or (action == "BUY" and ret_15m > 0.3):
                            tf_clues.append(f"15m momentum {ret_15m:+.1f}% confirms")
                        elif (action == "SELL" and ret_15m > 0.5) or (action == "BUY" and ret_15m < -0.5):
                            tf_clues.append(f"15m momentum {ret_15m:+.1f}% diverges")
                    if c4h is not None and len(c4h) >= 2:
                        ret_4h = float(c4h[-1] / c4h[-2] - 1) * 100
                        if (action == "SELL" and ret_4h < 0) or (action == "BUY" and ret_4h > 0):
                            tf_clues.append(f"4h trend {ret_4h:+.1f}% aligned")
                        else:
                            tf_clues.append(f"4h trend {ret_4h:+.1f}% counter")
                    if tf_clues:
                        parts.append("; ".join(tf_clues))

                    # 3. RSI context
                    rsi_val = _rsi(closes)
                    if rsi_val > 70:
                        parts.append(f"RSI {rsi_val:.0f} — overbought, downside risk elevated")
                    elif rsi_val > 60:
                        parts.append(f"RSI {rsi_val:.0f} — bullish territory")
                    elif rsi_val < 30:
                        parts.append(f"RSI {rsi_val:.0f} — oversold, bounce risk elevated")
                    elif rsi_val < 40:
                        parts.append(f"RSI {rsi_val:.0f} — bearish territory")
                    else:
                        parts.append(f"RSI {rsi_val:.0f} — neutral")

                    # 4. Price position vs recent range
                    if len(closes) >= 20:
                        hi20 = float(np.max(highs[-20:]))
                        lo20 = float(np.min(lows[-20:]))
                        rng  = hi20 - lo20
                        pos  = (closes[-1] - lo20) / rng if rng > 0 else 0.5
                        if pos > 0.80:
                            parts.append("Near 20-bar high — extended")
                        elif pos < 0.20:
                            parts.append("Near 20-bar low — compressed")
                        else:
                            parts.append(f"Mid-range ({pos:.0%} of 20-bar range)")

                    # 5. Funding rate
                    if funding_rates and len(funding_rates) > 0:
                        fr = funding_rates[-1]
                        if fr > 0.001:
                            parts.append(f"Funding +{fr*100:.3f}% — longs paying, bearish lean")
                        elif fr < -0.001:
                            parts.append(f"Funding {fr*100:.3f}% — shorts paying, bullish lean")
                        elif abs(fr) > 0.0003:
                            parts.append(f"Funding {'+' if fr >= 0 else ''}{fr*100:.3f}%")

                    # 6. BTC context
                    if btc_returns_arr is not None and len(btc_returns_arr) >= 3:
                        btc_1h = float(np.sum(btc_returns_arr[-3:])) * 100
                        if abs(btc_1h) > 0.5:
                            if (action == "SELL" and btc_1h < 0) or (action == "BUY" and btc_1h > 0):
                                parts.append(f"BTC {btc_1h:+.1f}% supports signal")
                            else:
                                parts.append(f"BTC {btc_1h:+.1f}% diverges from signal")

                    rationale = " · ".join(parts)
                else:
                    action, confidence, rationale = _score_heuristic(closes)

                results.append(SignalResult(
                    ticker=sym,
                    action=action,
                    confidence=round(confidence, 2),
                    rationale=rationale,
                ))
            except Exception as e:
                print(f"[signal_engine] {sym} error: {e}")
                continue

        return results

    return await asyncio.to_thread(_run)
