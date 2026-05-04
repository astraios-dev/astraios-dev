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
    "MATICUSDT", "AAVEUSDT",
    # Tier 3 — below baseline, signals informational only
    "SUIUSDT", "ARBUSDT", "1000PEPEUSDT", "WIFUSDT",
    "NEARUSDT", "INJUSDT",
    # FTMUSDT excluded — model overfit (100% acc / 0% directional), unreliable
]

FEATURE_COLS = [
    "returns",
    "ema_ratio_8", "ema_ratio_21", "ema_ratio_50",
    "close_position",
    "rsi_14",
    "macd_hist",
    "bb_pct",
    "mom_20",
    "atr_norm",
    "rolling_vol_5", "rolling_vol_20",
    "vol_ratio",
    "taker_buy_ratio", "taker_buy_pressure",
    "ret_lag_1", "ret_lag_3",
    "funding_rate", "funding_rate_ma8",
    "btc_returns", "btc_mom_5",
    "btc_vol_ratio", "btc_trend",
    "vol_regime", "trend_strength", "price_vs_sma200",
    "btc_corr_20", "funding_divergence",
]

LABEL_MAP_2 = {0: "SELL", 1: "BUY"}
LABEL_MAP_3 = {0: "SELL", 1: "HOLD", 2: "BUY"}

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


def _predict_symbol(closes, highs, lows, volumes, taker_buy_ratios=None,
                    funding_rates=None, open_interests=None, ls_ratios=None,
                    btc_returns=None, btc_mom_5=None,
                    btc_vol_ratio=None, btc_trend=None, btc_funding=None,
                    seq_len=32):
    import torch

    n = len(closes)
    feats = _engineer(closes, highs, lows, volumes, taker_buy_ratios)
    feats = _add_market_microstructure(feats, funding_rates, open_interests, ls_ratios, n)

    def _align(arr, n, fill):
        if arr is not None and len(arr) > 0:
            a = np.array(arr, dtype=np.float32)
            if len(a) >= n:
                return a[-n:]
            return np.concatenate([np.full(n - len(a), fill, dtype=np.float32), a])
        return np.full(n, fill, dtype=np.float32)

    feats["btc_returns"]   = _align(btc_returns, n, 0.0)
    feats["btc_mom_5"]     = _align(btc_mom_5, n, 0.0)
    feats["btc_vol_ratio"] = _align(btc_vol_ratio, n, 1.0)
    feats["btc_trend"]     = _align(btc_trend, n, 0.0)

    # Regime features from engineered data
    ret = feats["returns"]
    rv5  = np.array([np.std(ret[max(0,i-4):i+1]) for i in range(n)], dtype=np.float32)
    rv20 = np.array([np.std(ret[max(0,i-19):i+1]) for i in range(n)], dtype=np.float32)
    feats["vol_regime"] = np.clip(rv5 / np.maximum(rv20, 1e-9), 0, 5)

    ema50 = feats.get("ema_50", np.full(n, closes[-1]))
    atr14 = feats.get("atr_14", np.ones(n))
    slope = np.concatenate([[0.0]*5, (ema50[5:] - ema50[:-5]) / np.maximum(atr14[5:], 1e-9)])
    feats["trend_strength"] = np.clip(slope, -5, 5)

    sma200 = np.array([np.mean(closes[max(0,i-199):i+1]) for i in range(n)], dtype=np.float32)
    feats["price_vs_sma200"] = np.clip((closes - sma200) / np.maximum(sma200, 1e-9), -1, 1)

    # Rolling correlation with BTC
    btc_ret = _align(btc_returns, n, 0.0)
    sym_ret = ret
    corr = np.zeros(n, dtype=np.float32)
    for i in range(20, n):
        s = sym_ret[i-20:i]; b = btc_ret[i-20:i]
        ss, sb = np.std(s), np.std(b)
        if ss > 0 and sb > 0:
            corr[i] = float(np.corrcoef(s, b)[0, 1])
    feats["btc_corr_20"] = corr

    # Funding divergence: symbol funding - BTC funding
    sym_fr = feats.get("funding_rate", np.zeros(n))
    btc_fr = _align(btc_funding, n, 0.0)
    feats["funding_divergence"] = sym_fr - btc_fr

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

    # Confidence gate: require margin |p_buy - p_sell| > 0.10
    # Below this threshold the model has no real edge — emit as HOLD equiv
    if _config.get("n_classes") == 2:
        margin = abs(float(probs[1]) - float(probs[0]))
        if margin < 0.10:
            return None  # caller will skip or fall back to heuristic

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
                taker_buy_ratios = None

                # Fetch funding rates (public endpoint)
                funding_rates = None
                try:
                    fr_resp = client.get_funding_rate_history(category="linear", symbol=sym, limit=50)
                    if fr_resp["retCode"] == 0 and fr_resp["result"]["list"]:
                        funding_rates = [float(r["fundingRate"]) for r in reversed(fr_resp["result"]["list"])]
                except Exception:
                    pass

                if model_ready:
                    result = _predict_symbol(closes, highs, lows, volumes,
                                             taker_buy_ratios, funding_rates,
                                             None, None,
                                             btc_returns_arr, btc_mom5_arr,
                                             btc_vol_ratio_arr, btc_trend_arr, btc_funding_arr,
                                             _config["seq_len"])
                    if result is None:
                        continue
                    pred_class, confidence, probs = result
                    label_map = LABEL_MAP_2 if _config["n_classes"] == 2 else LABEL_MAP_3
                    action = label_map[pred_class]

                    rationale_parts = [f"Transformer: {action} ({confidence:.0%} conf)"]
                    if _config["n_classes"] == 2:
                        sell_p, buy_p = probs[0], probs[1]
                        rationale_parts.append(f"buy_p={buy_p:.2f} sell_p={sell_p:.2f}")
                    else:
                        sell_p, hold_p, buy_p = probs[0], probs[1], probs[2]
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
