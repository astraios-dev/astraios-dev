"""Generate Astraios technical whitepaper as PDF — v5, May 2026."""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
import os

OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "astraios-whitepaper.pdf")
os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)

W, H = A4
MARGIN = 22 * mm

INK    = colors.HexColor("#0a0a0a")
MUTED  = colors.HexColor("#555555")
ACCENT = colors.HexColor("#2ecb71")
LINE   = colors.HexColor("#dddddd")
SOFT   = colors.HexColor("#f7f7f7")
RED    = colors.HexColor("#e04040")
BLUE   = colors.HexColor("#2563eb")

def style(name, **kw):
    return ParagraphStyle(name, **kw)

S_TITLE  = style("Title",  fontName="Helvetica-Bold", fontSize=30, textColor=INK, leading=36, spaceAfter=4)
S_SUB    = style("Sub",    fontName="Helvetica", fontSize=13, textColor=MUTED, leading=18, spaceAfter=2)
S_META   = style("Meta",   fontName="Helvetica", fontSize=9, textColor=MUTED, leading=14)
S_H1     = style("H1",     fontName="Helvetica-Bold", fontSize=15, textColor=INK, leading=20, spaceBefore=18, spaceAfter=6)
S_H2     = style("H2",     fontName="Helvetica-Bold", fontSize=11, textColor=INK, leading=15, spaceBefore=12, spaceAfter=4)
S_H3     = style("H3",     fontName="Helvetica-BoldOblique", fontSize=10, textColor=MUTED, leading=14, spaceBefore=8, spaceAfter=3)
S_BODY   = style("Body",   fontName="Helvetica", fontSize=9.5, textColor=INK, leading=15, spaceAfter=5, alignment=TA_JUSTIFY)
S_BULLET = style("Bullet", fontName="Helvetica", fontSize=9.5, textColor=INK, leading=14, spaceAfter=3, leftIndent=14)
S_CODE   = style("Code",   fontName="Courier", fontSize=8.5, textColor=INK, leading=13, spaceAfter=2, leftIndent=10, backColor=SOFT)
S_CAPTION= style("Cap",    fontName="Helvetica-Oblique", fontSize=8, textColor=MUTED, leading=12, spaceAfter=4, alignment=TA_CENTER)

def hr():  return HRFlowable(width="100%", thickness=0.5, color=LINE, spaceAfter=8, spaceBefore=4)
def hr2(): return HRFlowable(width="100%", thickness=2,   color=ACCENT, spaceAfter=10)
def h1(t): return [Spacer(1,4), Paragraph(t, S_H1), hr()]
def h2(t): return [Paragraph(t, S_H2)]
def h3(t): return [Paragraph(t, S_H3)]
def p(t):  return Paragraph(t, S_BODY)
def b(t):  return Paragraph(f"• {t}", S_BULLET)
def sp(n=6): return Spacer(1, n)

def tbl(data, widths, header=True):
    t = Table(data, colWidths=widths)
    cmds = [
        ("FONTNAME",     (0,0),(-1,-1), "Helvetica"),
        ("FONTSIZE",     (0,0),(-1,-1), 8.5),
        ("TEXTCOLOR",    (0,0),(-1,-1), INK),
        ("ROWBACKGROUNDS",(0,0),(-1,-1), [colors.white, SOFT]),
        ("GRID",         (0,0),(-1,-1), 0.3, LINE),
        ("VALIGN",       (0,0),(-1,-1), "TOP"),
        ("TOPPADDING",   (0,0),(-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
        ("LEFTPADDING",  (0,0),(-1,-1), 6),
    ]
    if header:
        cmds += [
            ("BACKGROUND", (0,0),(-1,0), INK),
            ("TEXTCOLOR",  (0,0),(-1,0), colors.white),
            ("FONTNAME",   (0,0),(-1,0), "Helvetica-Bold"),
        ]
    t.setStyle(TableStyle(cmds))
    return t


def build():
    doc = SimpleDocTemplate(
        OUTPUT, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN,  bottomMargin=MARGIN,
        title="Astraios Technical Whitepaper v2",
        author="Astraios",
    )
    story = []

    # ── Cover ──────────────────────────────────────────────────────────────
    story += [
        Spacer(1, 28),
        Paragraph("ASTRAIOS", S_TITLE),
        Paragraph("Technical Whitepaper", S_SUB),
        Spacer(1, 6),
        hr2(),
        Paragraph("Quantitative ML Trading Platform · v2.0 · May 2026", S_META),
        Spacer(1, 8),
        p("Astraios is a full-stack quantitative trading platform for cryptocurrency "
          "derivatives. It combines a CNN-Transformer signal engine trained on 27 USDT "
          "perpetual futures, real-time Bybit mainnet and demo execution, an autonomous "
          "auto-trader with per-user risk controls, and a React/FastAPI dashboard with "
          "1-second live position updates. The v5 model achieves 55.3% directional "
          "accuracy with a Sharpe ratio of +5.52 and +0.65% expected value per trade "
          "at 2:1 risk-reward — validated on a 41,634-sample out-of-sample test set."),
        PageBreak(),
    ]

    # ── Table of Contents ──────────────────────────────────────────────────
    story += h1("Contents")
    toc = [
        "1.  System Architecture",
        "2.  MarketTransformer v5 — Signal Engine",
        "3.  Feature Engineering (28 Features)",
        "4.  Data Collection Pipeline",
        "5.  Labelling: Return-Quantile Method",
        "6.  Training Procedure",
        "7.  Backtesting & Evaluation",
        "8.  Inference Pipeline",
        "9.  Auto-Trader",
        "10. REST API Reference",
        "11. Bybit Integration & Demo Mode",
        "12. Database Schema",
        "13. Security Model",
        "14. AWS SageMaker Pipeline",
        "15. Frontend Architecture",
        "16. Signal Symbol Universe",
    ]
    for item in toc:
        story.append(b(item))
    story.append(PageBreak())

    # ── 1. System Architecture ─────────────────────────────────────────────
    story += h1("1. System Architecture")
    story += [
        p("Astraios follows a monorepo structure: a Python FastAPI backend, a React SPA, "
          "PostgreSQL persistence, and a decoupled ML pipeline for AWS SageMaker training. "
          "All services run from a single uvicorn process on a Linux EC2 instance. Bybit "
          "calls are proxied through a US-exit HTTP proxy to bypass regional API blocks."),
        sp(),
    ]
    story.append(tbl([
        ["Layer",          "Technology",                     "Role"],
        ["API Server",     "FastAPI + Uvicorn",              "REST endpoints, SPA serving, lifespan hooks"],
        ["Database",       "PostgreSQL + asyncpg",           "Users, signals, positions, auto-trade logs"],
        ["Background Jobs","asyncio tasks",                  "Signal refresh 15 min · price refresh 5 min · auto-trader"],
        ["Market Data",    "Bybit v5 API + Binance Futures", "Klines, tickers, OI, funding, L/S ratio"],
        ["ML Engine",      "PyTorch + AWS SageMaker",        "CNN-Transformer training and inference"],
        ["Frontend",       "React 19 + Vite 6",              "SPA: dashboard, charts, trade terminal, auto-trade"],
        ["Charts",         "lightweight-charts v4",          "Candlestick + volume, 1 s poll"],
        ["Auth",           "JWT (python-jose) + bcrypt",     "Per-user, 24h expiry"],
        ["API Key Crypto", "Fernet symmetric encryption",    "Bybit keys encrypted at rest in PostgreSQL"],
        ["Rate Limiting",  "slowapi",                        "5/min login · 10/min register · 10/min orders"],
        ["Migrations",     "Alembic",                        "Schema versioning"],
        ["Proxy",          "HTTP/HTTPS forward proxy",       "Routes Bybit/Binance calls from US IP"],
    ], [38*mm, 45*mm, 83*mm]))
    story.append(sp(10))

    story += h2("1.1 Data Flow")
    story += [
        p("On startup the lifespan hook creates all tables and launches three background "
          "tasks. Signal generation runs every 15 minutes per symbol: fetch 200 1h candles "
          "from Bybit, engineer 28 features, run the MarketTransformer, apply the "
          "confidence gate (|p_buy − p_sell| ≥ 0.10), write one signal per ticker per user "
          "to PostgreSQL, then invoke the auto-trader for all enabled users. Price refresh "
          "runs every 5 minutes for open paper positions. The frontend polls Bybit wallet "
          "and positions every 1 second via separate browser fetch loops."),
        sp(8),
    ]

    # ── 2. Model ────────────────────────────────────────────────────────────
    story += h1("2. MarketTransformer v5 — Signal Engine")
    story += [
        p("The signal engine is a CNN-Transformer architecture. A parallel 1D CNN "
          "front-end extracts local candlestick patterns (3-, 5-, and 7-bar windows) "
          "before the Transformer encoder attends to 48 bars of context. The model "
          "outputs a binary classification: BUY (label 1) or SELL (label 0), trained "
          "on return-quantile labels derived from 24-bar forward returns."),
        sp(),
    ]
    story.append(tbl([
        ["Component",              "Configuration"],
        ["CNN front-end",          "3 parallel Conv1d (kernel 3/5/7, d_model//3 channels each) → GELU → concat"],
        ["d_model",                "66 (22 channels × 3 CNN paths)"],
        ["Positional encoding",    "Sinusoidal, max_len=48"],
        ["Encoder layers",         "3 × TransformerEncoderLayer (pre-norm)"],
        ["Attention heads",        "2"],
        ["Feed-forward dim",       "256"],
        ["Activation",             "GELU"],
        ["Dropout",                "0.15 (training) / 0.0 (inference)"],
        ["Classification head",    "Linear(66→256) → GELU → Dropout → Linear(256→2)"],
        ["Output",                 "2 logits → softmax → BUY/SELL + confidence"],
        ["Sequence length",        "48 bars (48 hours of 1h candles)"],
        ["Input features",         "28"],
        ["Total parameters",       "~85K"],
        ["Model size",             "328 KB (model.pt)"],
    ], [60*mm, 108*mm]))
    story.append(sp(10))

    story += h2("2.1 Why CNN + Transformer")
    story += [
        p("A pure Transformer struggles to learn short-range candlestick structure "
          "(engulfing patterns, hammer/doji, 3-bar momentum bursts) because self-attention "
          "is permutation-equivariant — it has no inductive bias for local ordering. The "
          "parallel CNN front-end gives the model explicit local receptive fields at 3h, "
          "5h, and 7h windows before the Transformer encoder captures long-range "
          "dependencies across the full 48-bar sequence."),
        sp(8),
    ]

    # ── 3. Feature Engineering ─────────────────────────────────────────────
    story += h1("3. Feature Engineering — 28 Features")
    story += [
        p("All features are computed per-symbol from raw OHLCV kline data collected from "
          "Binance Futures (funding rates, klines) and Bybit (open interest, long/short). "
          "A StandardScaler fitted on training data (no val leakage) normalises inputs; "
          "scaler parameters are saved in config.json for consistent inference. Values are "
          "clipped to ±5σ before entering the model."),
        sp(),
    ]
    story.append(tbl([
        ["Feature",             "Description",                                  "Group"],
        ["returns",             "1-bar pct_change(close)",                      "Price"],
        ["ema_ratio_8",         "close / EMA(close, 8)",                        "Trend"],
        ["ema_ratio_21",        "close / EMA(close, 21)",                       "Trend"],
        ["ema_ratio_50",        "close / EMA(close, 50)",                       "Trend"],
        ["close_position",      "(close − low) / (high − low)",                 "Price"],
        ["rsi_14",              "RSI(14)",                                       "Momentum"],
        ["macd_hist",           "MACD(12,26) − Signal(9)",                      "Momentum"],
        ["bb_pct",              "(close − BB_lower) / (BB_upper − BB_lower)",   "Momentum"],
        ["mom_20",              "close / close[−20] − 1",                       "Momentum"],
        ["atr_norm",            "ATR(14) / close",                              "Volatility"],
        ["rolling_vol_5",       "std(returns, 5)",                              "Volatility"],
        ["rolling_vol_20",      "std(returns, 20)",                             "Volatility"],
        ["vol_ratio",           "volume / MA(volume, 20)",                      "Volume"],
        ["taker_buy_ratio",     "taker_buy_vol / total_vol",                    "Volume"],
        ["taker_buy_pressure",  "(taker_buy_ratio − 0.5) × vol_ratio",         "Volume"],
        ["ret_lag_1",           "returns shifted 1 bar",                        "Lag"],
        ["ret_lag_3",           "returns shifted 3 bars",                       "Lag"],
        ["funding_rate",        "Binance 8h funding rate (ffilled to 1h)",      "Microstructure"],
        ["funding_rate_ma8",    "8-bar rolling mean of funding_rate",           "Microstructure"],
        ["btc_returns",         "Bitcoin 1-bar return (cross-asset)",           "Cross-asset"],
        ["btc_mom_5",           "BTC close / BTC close[−5] − 1",               "Cross-asset"],
        ["btc_vol_ratio",       "BTC rv5 / BTC rv20 (vol expansion proxy)",    "Cross-asset"],
        ["btc_trend",           "sign(BTC close − BTC EMA50)",                 "Cross-asset"],
        ["vol_regime",          "rv5 / rv20 (symbol vol expansion)",            "Regime"],
        ["trend_strength",      "EMA50 slope / ATR (ADX proxy)",               "Regime"],
        ["price_vs_sma200",     "(close − SMA200) / SMA200, clipped ±1",       "Regime"],
        ["btc_corr_20",         "20-bar rolling Pearson corr vs BTC returns",  "Regime"],
        ["funding_divergence",  "symbol_funding − btc_funding",                "Regime"],
    ], [38*mm, 84*mm, 28*mm]))
    story.append(sp(10))

    # ── 4. Data Collection ─────────────────────────────────────────────────
    story += h1("4. Data Collection Pipeline")
    story += [
        p("Training data is collected by ml/collect_data.py. Binance Futures is used as "
          "the primary klines and funding rate source (deeper history than Bybit). Bybit "
          "provides open interest and long/short ratios for recent bars. All API calls are "
          "proxied through the same HTTP proxy as production."),
        sp(),
    ]
    story.append(tbl([
        ["Source",          "Data",                          "Coverage"],
        ["Binance Futures",  "1h OHLCV klines",              "3 years for majors, 18 months for alts"],
        ["Binance Futures",  "8h funding rate history",      "Full history paginated"],
        ["BTC reference",    "BTC klines + funding",         "3 years, fetched first as cross-asset base"],
    ], [40*mm, 60*mm, 68*mm]))
    story += [
        sp(8),
        p("A data quality gate rejects any symbol where more than 50% of return bars are "
          "exactly zero — this filters delisted or illiquid assets that would corrupt "
          "quantile labels (e.g. FTM after delisting). The gate is applied immediately "
          "after kline fetch before any feature engineering."),
        sp(8),
    ]
    story.append(tbl([
        ["Parameter",         "Value"],
        ["Symbols",           "27 USDT perpetuals"],
        ["Majors (3yr)",      "BTC, ETH, BNB, SOL, XRP, DOGE, AVAX, LINK, ADA, MATIC, LTC, DOT, ATOM, TRX"],
        ["Alts (18mo)",       "AAVE, UNI, SUI, ARB, OP, APT, NEAR, INJ, TIA, SEI, WIF, 1000PEPE, BONK, LDO"],
        ["Excluded",          "FTMUSDT — 75% zero-return bars due to delisting artefact"],
        ["Total samples",     "187,515 after feature engineering and quality filtering"],
        ["Label balance",     "SELL 91,250 (48.7%) / BUY 96,265 (51.3%)"],
    ], [55*mm, 113*mm]))
    story.append(sp(10))

    # ── 5. Labelling ──────────────────────────────────────────────────────
    story += h1("5. Labelling: Return-Quantile Method")
    story += [
        p("Labels are computed per-symbol using a return-quantile approach rather than "
          "fixed ATR barriers. For each bar, the 24-bar forward return is computed. The "
          "top 30th percentile of forward returns within that symbol's distribution is "
          "labelled BUY=1; the bottom 30th percentile is labelled SELL=0. The middle 40% "
          "is discarded — these bars represent ambiguous outcomes that add noise without "
          "learnable signal."),
        sp(),
        p("This approach has two key advantages over fixed barriers: (1) it adapts to each "
          "symbol's volatility regime automatically — a 3% move on SOL and a 3% move on "
          "BTC carry different statistical significance; (2) it guarantees a near-equal "
          "class distribution regardless of market direction, removing the need for "
          "asymmetric class weights."),
        sp(),
    ]
    story.append(tbl([
        ["Property",         "Value"],
        ["Label horizon",    "24 bars (24 hours at 1h resolution)"],
        ["BUY threshold",    "Top 30th percentile of 24h forward return for that symbol"],
        ["SELL threshold",   "Bottom 30th percentile of 24h forward return for that symbol"],
        ["Dropped",          "Middle 40% — ambiguous return outcomes"],
        ["Result",           "Per-symbol balanced binary labels, adapts to volatility regime"],
    ], [55*mm, 113*mm]))
    story.append(sp(10))

    # ── 6. Training ────────────────────────────────────────────────────────
    story += h1("6. Training Procedure")

    story += h2("6.1 Per-Symbol Walk-Forward Cross-Validation")
    story += [
        p("Training uses a per-symbol expanding walk-forward split with a 24-bar embargo "
          "gap between train and validation windows. The embargo prevents label leakage "
          "from the 24-bar quantile label horizon — without it, a bar near the train/val "
          "boundary in the training set would have its label computed from bars in the "
          "validation set."),
        sp(),
        p("For each fold and each symbol independently: the first 78% of chronological "
          "rows form the training window; the next 22% form the validation window with "
          "a 24-bar gap in between. Masks are unioned across all symbols per fold. This "
          "prevents cross-symbol contamination: BTC validation data never overlaps with "
          "ETH training data from the same calendar period."),
        sp(),
    ]
    story.append(tbl([
        ["Parameter",         "Value"],
        ["CV folds",          "3 (expanding windows per symbol)"],
        ["Train fraction",    "~78% per symbol per fold"],
        ["Val fraction",      "~22% per symbol per fold"],
        ["Embargo",           "24 bars between train and val (matches label horizon)"],
        ["Scaler fitting",    "StandardScaler fitted on train split only — no val leakage"],
        ["Feature clipping",  "±5σ after scaling"],
    ], [55*mm, 113*mm]))
    story.append(sp(8))

    story += h2("6.2 Loss Function: Cost-Sensitive Focal Loss")
    story += [
        p("Training uses a custom focal loss that combines standard focal weighting "
          "(γ=2.0, down-weights easy examples) with an asymmetric cost multiplier "
          "(cost_wrong=2.0) that penalises confident wrong predictions twice as hard. "
          "This matters for trading: a high-confidence incorrect signal causes larger "
          "losses than an uncertain one."),
        sp(),
    ]

    story += h2("6.3 Hyperparameters")
    story.append(tbl([
        ["Hyperparameter",   "Value"],
        ["Epochs",           "50 (with patience=10 early stopping)"],
        ["Batch size",       "512"],
        ["Optimizer",        "AdamW (lr=3e-4, weight_decay=1e-4)"],
        ["LR schedule",      "CosineAnnealingLR (T_max=50, η_min=lr×0.01)"],
        ["Loss",             "Cost-sensitive focal loss (γ=2.0, cost_wrong=2.0)"],
        ["Gradient clipping","1.0 (max norm)"],
        ["Instance type",    "AWS SageMaker ml.g5.12xlarge (4× NVIDIA A10G GPU)"],
    ], [55*mm, 113*mm]))
    story.append(sp(10))

    # ── 7. Backtesting ──────────────────────────────────────────────────────
    story += h1("7. Backtesting & Evaluation")
    story += [
        p("Evaluation uses a proper TP/SL simulation over the out-of-sample validation "
          "set (41,634 samples across 27 symbols). For each predicted signal, a position "
          "is entered at the signal bar's close price. Subsequent bars are scanned for TP "
          "or SL hits; if neither is hit within the 24-bar horizon, the trade exits at the "
          "horizon price. A round-trip fee of 0.08% (2 × 0.04% Bybit taker) is deducted "
          "from each trade."),
        sp(),
    ]
    story.append(tbl([
        ["Metric",              "All signals",  "Conf ≥ 60%",  "Conf ≥ 65%"],
        ["Val accuracy",        "55.3%",        "—",           "—"],
        ["Win rate (TP hit)",   "49.6%",        "49.8%",       "49.6%"],
        ["Avg trade return",    "+0.649%",       "+0.661%",     "+0.654%"],
        ["Profit factor",       "1.82",         "1.83",        "1.82"],
        ["Sharpe ratio",        "+5.52",        "+5.62",       "+5.55"],
        ["Avg win",             "+2.911%",       "+2.918%",     "+2.920%"],
        ["Avg loss",            "−1.577%",       "−1.580%",     "−1.580%"],
        ["Total val PnL",       "+27,025%",     "+10,448%",    "+5,706%"],
        ["Trade count (val)",   "41,634",       "15,796",      "8,732"],
    ], [52*mm, 36*mm, 36*mm, 36*mm]))
    story.append(sp(8))
    story += [
        p("The model's positive EV derives from the asymmetric risk-reward setup rather "
          "than a high win rate. At TP=3%/SL=1.5% (2:1 R:R), break-even requires only "
          "33.3% wins; the model achieves ~49.6%, yielding a theoretical EV of "
          "0.496×3% − 0.504×1.5% − 0.08% = +0.65% per trade."),
        sp(),
        p("Confidence filtering (≥0.65) improves trade quality marginally but the win "
          "rate plateau at 49–50% across all confidence bins indicates the win rate is "
          "determined by the R:R geometry, not model confidence. The correct lever for "
          "higher absolute returns is a wider R:R ratio, not a confidence gate."),
        sp(8),
    ]

    story += h2("7.1 Per-Symbol Sharpe (Top 10)")
    story.append(tbl([
        ["Symbol",      "Val Acc", "Sharpe",  "Trades"],
        ["MATICUSDT",   "58.9%",   "+20.44",  "856"],
        ["XRPUSDT",     "57.6%",   "+11.19",  "1,985"],
        ["LTCUSDT",     "57.3%",   "+9.17",   "2,054"],
        ["TIAUSDT",     "54.3%",   "+8.87",   "1,078"],
        ["WIFUSDT",     "52.0%",   "+8.07",   "1,122"],
        ["ETHUSDT",     "55.7%",   "+8.40",   "1,949"],
        ["SOLUSDT",     "57.3%",   "+8.38",   "2,124"],
        ["INJUSDT",     "51.9%",   "+7.40",   "1,090"],
        ["LINKUSDT",    "56.2%",   "+5.29",   "2,075"],
        ["BNBUSDT",     "54.8%",   "+5.16",   "2,059"],
    ], [38*mm, 28*mm, 28*mm, 28*mm]))
    story.append(sp(10))

    story += h2("7.2 Model Calibration")
    story += [
        p("The model is well-calibrated with an Expected Calibration Error (ECE) of 0.04. "
          "Higher-confidence predictions correspond to meaningfully higher accuracy:"),
        sp(),
    ]
    story.append(tbl([
        ["Confidence bin", "Count",  "Avg conf", "Accuracy", "ECE gap"],
        ["0.50 – 0.60",    "25,838", "54.7%",    "52.7%",    "+0.020"],
        ["0.60 – 0.70",    "11,304", "64.2%",    "56.7%",    "+0.074"],
        ["0.70 – 0.80",    " 4,361", "74.2%",    "66.8%",    "+0.075"],
        ["0.80 – 0.90",    "   131", "80.5%",    "69.5%",    "+0.111"],
    ], [40*mm, 28*mm, 28*mm, 28*mm, 28*mm]))
    story.append(sp(10))

    # ── 8. Inference Pipeline ──────────────────────────────────────────────
    story += h1("8. Inference Pipeline")
    story += [
        p("The model singleton loads from ml/output/model.pt and ml/output/config.json "
          "once at application startup. For each of 20 symbols every 15 minutes:"),
        sp(),
        b("Fetch 200 most recent 1h candles from Bybit via the configured proxy"),
        b("Fetch BTC klines + funding once for cross-asset features"),
        b("Fetch per-symbol funding rate history (50 bars)"),
        b("Engineer all 28 features using the same computation graph as training"),
        b("Scale using saved scaler mean/scale; clip to ±5σ"),
        b("Slice the last 48 timesteps as the model input sequence"),
        b("Forward pass through CNN front-end → Transformer → head → softmax"),
        b("Apply confidence gate: skip signal if |p_buy − p_sell| < 0.10"),
        b("Append RSI/funding context to the rationale string"),
        b("Fall back to heuristic momentum scoring if model weights are absent"),
        sp(8),
    ]

    # ── 9. Auto-Trader ─────────────────────────────────────────────────────
    story += h1("9. Auto-Trader")
    story += [
        p("The auto-trader runs automatically after every signal refresh cycle. For each "
          "user with auto-trading enabled, it fetches live positions and wallet equity, "
          "closes positions where the signal has flipped or confidence has dropped below "
          "threshold, and opens new positions for qualifying signals within the configured "
          "risk limits. All actions are logged to the auto_trade_logs table."),
        sp(),
    ]
    story.append(tbl([
        ["Parameter",             "Default",   "Description"],
        ["enabled",               "false",     "Master on/off switch"],
        ["demo",                  "true",      "Use Bybit Demo (api-demo.bybit.com) by default"],
        ["confidence_threshold",  "0.65",      "Minimum model confidence to enter a trade"],
        ["max_positions",         "3",         "Maximum concurrent auto-trade positions"],
        ["position_size_pct",     "5%",        "Equity percentage per position"],
        ["leverage",              "1×",        "Position leverage"],
        ["tp_pct",                "3.0%",      "Take-profit distance from entry"],
        ["sl_pct",                "1.5%",      "Stop-loss distance from entry (2:1 R:R)"],
        ["daily_loss_limit",      "$50",       "Maximum daily loss before pausing"],
        ["symbols",               "8 majors",  "BTC/ETH/SOL/BNB/DOGE/LTC/TRX/XRP"],
    ], [48*mm, 25*mm, 95*mm]))
    story += [
        sp(8),
        p("Demo mode uses Bybit's demo trading environment (api-demo.bybit.com), which "
          "executes orders against live market prices with virtual funds. Demo API keys "
          "are stored in the same database fields as testnet keys and routed via "
          "pybit's demo=True flag. This enables full end-to-end testing of the auto-trader "
          "logic without financial risk."),
        sp(8),
    ]

    # ── 10. API Reference ──────────────────────────────────────────────────
    story += h1("10. REST API Reference")

    story += h2("10.1 Authentication")
    story += [
        p("All endpoints except /api/health require Bearer JWT. Tokens are issued on "
          "POST /api/auth/register and /api/auth/login, expire after 24h. "
          "Rate limits: login 5/min, register 10/min."),
        sp(),
    ]

    story += h2("10.2 Trade Endpoints")
    story.append(tbl([
        ["Method", "Path",                  "Description"],
        ["GET",    "/api/trade/klines",     "Klines (≤1,000 candles, paginated)"],
        ["GET",    "/api/trade/symbols",    "All USDT perps sorted by 24h volume"],
        ["GET",    "/api/trade/positions",  "Open positions (?demo=true for demo account)"],
        ["GET",    "/api/trade/wallet",     "Equity, available balance, unrealised PnL"],
        ["GET",    "/api/trade/orders",     "Open orders"],
        ["POST",   "/api/trade/order",      "Market order — symbol, side, qty, tp?, sl?"],
        ["POST",   "/api/trade/close",      "Close position (reverse market order)"],
        ["POST",   "/api/trade/leverage",   "Set symbol leverage"],
    ], [16*mm, 50*mm, 102*mm]))
    story.append(sp(8))

    story += h2("10.3 Auto-Trade Endpoints")
    story.append(tbl([
        ["Method", "Path",                     "Description"],
        ["GET",    "/api/auto-trade/config",   "Get user's auto-trade configuration"],
        ["POST",   "/api/auto-trade/config",   "Save auto-trade configuration"],
        ["GET",    "/api/auto-trade/stats",    "Aggregate stats: fills, errors, avg conf, hold time"],
        ["GET",    "/api/auto-trade/pnl",      "Closed P&L from Bybit history with summary metrics"],
        ["GET",    "/api/auto-trade/log",      "Raw trade log (last 50 actions)"],
    ], [16*mm, 54*mm, 98*mm]))
    story.append(sp(8))

    story += h2("10.4 Signal & Account Endpoints")
    story.append(tbl([
        ["Method", "Path",                          "Description"],
        ["GET",    "/api/signals",                  "Latest signal per ticker, sorted confidence DESC"],
        ["GET",    "/api/account/stats",            "Portfolio metrics, API key status"],
        ["GET",    "/api/account/model-info",       "Loaded model architecture and val accuracy"],
        ["POST",   "/api/account/api-keys",         "Save mainnet Bybit credentials (Fernet-encrypted)"],
        ["POST",   "/api/account/testnet-keys",     "Save demo Bybit credentials (Fernet-encrypted)"],
        ["POST",   "/api/market/refresh",           "Trigger manual signal + price refresh (2/min limit)"],
    ], [16*mm, 56*mm, 96*mm]))
    story.append(sp(10))

    # ── 11. Bybit Integration ──────────────────────────────────────────────
    story += h1("11. Bybit Integration & Demo Mode")
    story += [
        p("All Bybit calls use the pybit.unified_trading.HTTP client (v5 API, "
          "linear/USDT-perp category). Per-user API keys are retrieved from PostgreSQL, "
          "decrypted with Fernet, and passed to pybit for each request. The server-level "
          "BYBIT_API_KEY environment variable provides a fallback for unauthenticated "
          "public endpoints (klines, tickers)."),
        sp(),
    ]
    story.append(tbl([
        ["Mode",     "Endpoint",                   "Keys used",         "Notes"],
        ["Live",     "api.bybit.com",               "Mainnet API keys",  "Real money, real positions"],
        ["Demo",     "api-demo.bybit.com",           "Demo API keys",     "Virtual funds, live prices"],
        ["Public",   "api.bybit.com (no auth)",      "None",              "Klines, symbols, funding"],
    ], [22*mm, 48*mm, 40*mm, 58*mm]))
    story += [
        sp(8),
        p("Demo mode uses pybit's native demo=True parameter, which routes to Bybit's "
          "official demo trading environment. Demo keys are stored in the same "
          "bybit_testnet_key/secret fields in PostgreSQL and encrypted with Fernet."),
        sp(8),
    ]

    # ── 12. Database Schema ────────────────────────────────────────────────
    story += h1("12. Database Schema")

    story += h2("12.1 Users")
    story.append(tbl([
        ["Column",               "Type",          "Notes"],
        ["id",                   "UUID",           "Primary key, uuid4"],
        ["email",                "VARCHAR(320)",   "Unique, indexed"],
        ["hashed_password",      "VARCHAR(128)",   "bcrypt"],
        ["name",                 "VARCHAR(120)",   ""],
        ["plan",                 "VARCHAR(40)",    "Default 'Private Beta'"],
        ["bybit_api_key",        "VARCHAR(256)",   "Nullable, mainnet, Fernet-encrypted"],
        ["bybit_api_secret",     "VARCHAR(256)",   "Nullable, mainnet, Fernet-encrypted"],
        ["bybit_testnet_key",    "VARCHAR(256)",   "Nullable, demo, Fernet-encrypted"],
        ["bybit_testnet_secret", "VARCHAR(256)",   "Nullable, demo, Fernet-encrypted"],
    ], [50*mm, 38*mm, 80*mm]))
    story.append(sp(8))

    story += h2("12.2 Signals")
    story.append(tbl([
        ["Column",     "Type",         "Notes"],
        ["id",         "UUID",         "Primary key"],
        ["user_id",    "UUID",         "FK → users, indexed"],
        ["ticker",     "VARCHAR(20)",  "USDT perp symbol, indexed"],
        ["action",     "VARCHAR(10)",  "'BUY' or 'SELL'"],
        ["confidence", "FLOAT",        "[0.0, 1.0] softmax probability"],
        ["rationale",  "TEXT",         "Human-readable explanation"],
        ["created_at", "TIMESTAMPTZ",  "UTC"],
    ], [40*mm, 40*mm, 88*mm]))
    story.append(sp(8))

    story += h2("12.3 AutoTradeConfig")
    story.append(tbl([
        ["Column",               "Type",    "Notes"],
        ["user_id",              "UUID",    "FK → users, unique (one config per user)"],
        ["enabled",              "BOOLEAN", "Master toggle"],
        ["demo",                 "BOOLEAN", "Demo mode (default true)"],
        ["confidence_threshold", "FLOAT",   "Default 0.65"],
        ["max_positions",        "INT",     "Default 3"],
        ["position_size_pct",    "FLOAT",   "Default 5.0"],
        ["leverage",             "INT",     "Default 1"],
        ["tp_pct",               "FLOAT",   "Default 3.0"],
        ["sl_pct",               "FLOAT",   "Default 1.5"],
        ["daily_loss_limit",     "FLOAT",   "Default 50.0 USD"],
        ["symbols",              "TEXT",    "Comma-separated, default 8 majors"],
    ], [48*mm, 25*mm, 95*mm]))
    story.append(sp(10))

    # ── 13. Security ───────────────────────────────────────────────────────
    story += h1("13. Security Model")
    story += [
        b("Passwords hashed with bcrypt (passlib, 12 rounds)"),
        b("JWTs signed with HS256; secret rotatable via JWT_SECRET env var; 24h expiry"),
        b("Bybit API keys encrypted at rest with Fernet symmetric encryption; FERNET_KEY in .env"),
        b("Keys are decrypted in memory per-request, never returned to the client"),
        b("Per-user key isolation: each trade call resolves credentials from the authenticated user's DB row"),
        b("Input validation via Pydantic field_validators: symbol regex, side enum, qty/leverage range checks"),
        b("Rate limiting: 5/min login, 10/min register, 10/min order placement, 2/min signal refresh"),
        b("CORS restricted to configured origin list (ALLOWED_ORIGINS env var)"),
        b("Structured JSON request logging with request IDs and duration"),
        b("Global 500 handler suppresses stack traces from client responses"),
        sp(10),
    ]

    # ── 14. SageMaker ──────────────────────────────────────────────────────
    story += h1("14. AWS SageMaker Training Pipeline")
    story += [
        p("Training is triggered manually via ml/launch_sagemaker.py, which packages "
          "train.py into a tar.gz, uploads the dataset CSV to S3, and submits a "
          "CreateTrainingJob request using boto3. The training container is a pre-built "
          "PyTorch GPU image from the AWS ECR registry."),
        sp(),
    ]
    story.append(tbl([
        ["Parameter",     "Value"],
        ["Account",       "125499242423"],
        ["Region",        "us-east-1"],
        ["IAM Role",      "astrax (EC2 instance profile)"],
        ["S3 Bucket",     "astraiosbucket"],
        ["Training image","pytorch-training:2.1.0-gpu-py310-cu121-ubuntu20.04-sagemaker"],
        ["Instance",      "ml.g5.12xlarge (4× NVIDIA A10G, 48 GB VRAM total)"],
        ["Max runtime",   "7,200 seconds"],
        ["Output",        "model.pt + config.json → model.tar.gz → auto-downloaded to ml/output/"],
    ], [40*mm, 128*mm]))
    story.append(sp(10))

    # ── 15. Frontend ───────────────────────────────────────────────────────
    story += h1("15. Frontend Architecture")
    story += [
        p("The React SPA is built with Vite 6 and served by the FastAPI process via "
          "StaticFiles. Three routes: landing (/), login (/login), dashboard (/dashboard). "
          "No UI framework — pure CSS with design tokens matching the dark editorial theme "
          "(--paper:#050505, --ink:#fff, --accent:#2ecb71)."),
        sp(),
        b("React 19 with hooks; no class components"),
        b("lightweight-charts v4 — candlestick + volume panels, 1s live candle polling"),
        b("Global Live/Demo toggle — persisted in localStorage; switches all Bybit calls"),
        b("Mode-guarded fetch: in-flight requests from old mode are discarded on switch (modeRef pattern)"),
        b("Trade terminal: 546-symbol searchable selector, leverage (1–100×), quick-size buttons, TP/SL"),
        b("Auto-trade panel: Demo/Live toggle, 7 risk params, performance stats grid, realised P&L table"),
        b("Responsive breakpoints: 980px (tablet) and 640px (mobile)"),
        b("Signal cards tiered by confidence with colour-coded BUY/SELL badges"),
        sp(10),
    ]

    # ── 16. Symbol Universe ────────────────────────────────────────────────
    story += h1("16. Signal Symbol Universe")
    story += [
        p("The signal engine covers 20 USDT perpetual futures across three tiers. "
          "Tier 1 symbols (strong model edge, 55–59% val accuracy) are the default "
          "auto-trade candidates. Tier 2 provides informational signals. Tier 3 symbols "
          "are below the majority-class baseline and should not be auto-traded."),
        sp(),
    ]
    story.append(tbl([
        ["Symbol",        "Tier", "Val Acc", "Sharpe", "Notes"],
        ["BTCUSDT",       "1",    "56.4%",   "+1.93",  "Auto-trade default"],
        ["ETHUSDT",       "1",    "55.7%",   "+8.40",  "Auto-trade default"],
        ["SOLUSDT",       "1",    "57.3%",   "+8.38",  "Auto-trade default"],
        ["BNBUSDT",       "1",    "54.8%",   "+5.16",  "Auto-trade default"],
        ["DOGEUSDT",      "1",    "56.3%",   "-3.14",  "Auto-trade default"],
        ["LTCUSDT",       "1",    "57.3%",   "+9.17",  "Auto-trade default"],
        ["TRXUSDT",       "1",    "56.8%",   "-2.80",  "Auto-trade default"],
        ["XRPUSDT",       "1",    "57.6%",   "+11.19", "Auto-trade default"],
        ["AVAXUSDT",      "2",    "55.7%",   "+2.05",  "Informational"],
        ["LINKUSDT",      "2",    "56.2%",   "+5.29",  "Informational"],
        ["ADAUSDT",       "2",    "56.5%",   "+0.16",  "Informational"],
        ["DOTUSDT",       "2",    "56.7%",   "-3.00",  "Informational"],
        ["MATICUSDT",     "2",    "58.9%",   "+20.44", "Informational (low sample count)"],
        ["AAVEUSDT",      "2",    "52.7%",   "-2.27",  "Informational"],
        ["SUIUSDT",       "3",    "52.3%",   "+0.39",  "Below baseline"],
        ["ARBUSDT",       "3",    "53.4%",   "-1.24",  "Below baseline"],
        ["1000PEPEUSDT",  "3",    "52.9%",   "+6.05",  "Below baseline"],
        ["WIFUSDT",       "3",    "52.0%",   "+8.07",  "High vol, low acc"],
        ["NEARUSDT",      "3",    "53.9%",   "+3.09",  "Below baseline"],
        ["INJUSDT",       "3",    "51.9%",   "+7.40",  "Below baseline"],
    ], [32*mm, 14*mm, 22*mm, 22*mm, 78*mm]))
    story.append(sp(10))

    # ── Closing ────────────────────────────────────────────────────────────
    story += [
        PageBreak(),
        hr2(),
        Paragraph("Astraios · Technical Whitepaper v2.0 · May 2026", S_META),
        Spacer(1, 6),
        Paragraph(
            "This document describes the Astraios platform as of May 2026. "
            "Model performance metrics are out-of-sample backtests on historical data; "
            "past performance does not guarantee future results. "
            "Cryptocurrency derivatives trading involves significant risk of loss. "
            "Astraios is a technology platform — not investment advice.",
            S_CAPTION,
        ),
    ]

    doc.build(story)
    print(f"Written: {OUTPUT}")


if __name__ == "__main__":
    build()
