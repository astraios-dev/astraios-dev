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
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "SUIUSDT",
    "DOGEUSDT", "XRPUSDT", "LINKUSDT", "AAVEUSDT",
    "1000PEPEUSDT", "WIFUSDT", "ARBUSDT", "AVAXUSDT",
]

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
    "funding_rate", "funding_rate_ma8", "funding_rate_std8", "funding_cumulative",
    "oi_change", "oi_ratio", "oi_price_div",
    "long_short_ratio", "ls_ma8", "ls_change",
]

LABEL_MAP = {0: "SELL", 1: "HOLD", 2: "BUY"}

_model = None
_config = None
_scaler_mean = None
_scaler_scale = None


def _load_model():
    global _model, _config, _scaler_mean, _scaler_scale
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


def _engineer(closes, highs, lows, volumes):
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


def _predict_symbol(closes, highs, lows, volumes, funding_rates=None,
                    open_interests=None, ls_ratios=None, seq_len=32):
    import torch

    n = len(closes)
    feats = _engineer(closes, highs, lows, volumes)
    feats = _add_market_microstructure(feats, funding_rates, open_interests, ls_ratios, n)
    feat_matrix = _feats_to_matrix(feats)
    feat_matrix = np.nan_to_num(feat_matrix, nan=0.0, posinf=0.0, neginf=0.0)

    feat_matrix = (feat_matrix - _scaler_mean) / np.maximum(_scaler_scale, 1e-9)

    if len(feat_matrix) < seq_len:
        return None

    seq = feat_matrix[-seq_len:]
    x = torch.FloatTensor(seq).unsqueeze(0)

    with torch.no_grad():
        logits = _model(x)
        probs = torch.softmax(logits, dim=-1).squeeze().numpy()

    pred_class = int(np.argmax(probs))
    confidence = float(probs[pred_class])

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

        results = []
        for sym in symbols:
            try:
                resp = client.get_kline(category="linear", symbol=sym, interval="60", limit=200)
                if resp["retCode"] != 0:
                    continue
                rows = list(reversed(resp["result"]["list"]))
                closes  = np.array([float(r[4]) for r in rows], dtype=np.float32)
                highs   = np.array([float(r[2]) for r in rows], dtype=np.float32)
                lows    = np.array([float(r[3]) for r in rows], dtype=np.float32)
                volumes = np.array([float(r[5]) for r in rows], dtype=np.float32)

                # Fetch funding rates (public endpoint)
                funding_rates = None
                try:
                    fr_resp = client.get_funding_rate_history(category="linear", symbol=sym, limit=50)
                    if fr_resp["retCode"] == 0 and fr_resp["result"]["list"]:
                        funding_rates = [float(r["fundingRate"]) for r in reversed(fr_resp["result"]["list"])]
                except Exception:
                    pass

                # Open interest
                open_interests = None
                try:
                    oi_resp = client.get_open_interest(category="linear", symbol=sym, intervalTime="1h", limit=200)
                    if oi_resp["retCode"] == 0 and oi_resp["result"]["list"]:
                        open_interests = [float(r["openInterest"]) for r in reversed(oi_resp["result"]["list"])]
                except Exception:
                    pass

                # Long/short ratio
                ls_ratios = None
                try:
                    ls_resp = client.get_long_short_ratio(category="linear", symbol=sym, period="1h", limit=200)
                    if ls_resp["retCode"] == 0 and ls_resp["result"]["list"]:
                        ls_ratios = [float(r["buyRatio"]) / max(float(r["sellRatio"]), 1e-9)
                                     for r in reversed(ls_resp["result"]["list"])]
                except Exception:
                    pass

                if model_ready:
                    result = _predict_symbol(closes, highs, lows, volumes,
                                             funding_rates, open_interests, ls_ratios,
                                             _config["seq_len"])
                    if result is None:
                        continue
                    pred_class, confidence, probs = result
                    action = LABEL_MAP[pred_class]

                    sell_p, hold_p, buy_p = probs[0], probs[1], probs[2]
                    rationale_parts = [f"Transformer: {action} ({confidence:.0%} conf)"]
                    if action == "BUY":
                        rationale_parts.append(f"buy_p={buy_p:.2f} vs hold_p={hold_p:.2f}")
                    elif action == "SELL":
                        rationale_parts.append(f"sell_p={sell_p:.2f} vs hold_p={hold_p:.2f}")
                    else:
                        rationale_parts.append("no clear directional edge")

                    rsi_val = _rsi(closes)
                    if rsi_val > 70:
                        rationale_parts.append(f"RSI {rsi_val:.0f} overbought")
                    elif rsi_val < 30:
                        rationale_parts.append(f"RSI {rsi_val:.0f} oversold")

                    if funding_rates and len(funding_rates) > 0:
                        fr = funding_rates[-1]
                        if abs(fr) > 0.0005:
                            rationale_parts.append(f"funding {'+' if fr > 0 else ''}{fr*100:.3f}%")

                    rationale = ". ".join(rationale_parts) + "."
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
