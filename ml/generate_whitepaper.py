"""Generate Astraios technical whitepaper as PDF."""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
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

INK = colors.HexColor("#0a0a0a")
MUTED = colors.HexColor("#555555")
ACCENT = colors.HexColor("#2ecb71")
LINE = colors.HexColor("#dddddd")
SOFT = colors.HexColor("#f7f7f7")
RED = colors.HexColor("#e04040")

styles = getSampleStyleSheet()

def style(name, **kw):
    s = ParagraphStyle(name, **kw)
    return s

S_TITLE = style("WP_Title",
    fontName="Helvetica-Bold", fontSize=28, textColor=INK,
    leading=34, spaceAfter=4, alignment=TA_LEFT)

S_SUB = style("WP_Sub",
    fontName="Helvetica", fontSize=13, textColor=MUTED,
    leading=18, spaceAfter=2, alignment=TA_LEFT)

S_META = style("WP_Meta",
    fontName="Helvetica", fontSize=9, textColor=MUTED,
    leading=14, alignment=TA_LEFT)

S_H1 = style("WP_H1",
    fontName="Helvetica-Bold", fontSize=16, textColor=INK,
    leading=22, spaceBefore=18, spaceAfter=6)

S_H2 = style("WP_H2",
    fontName="Helvetica-Bold", fontSize=12, textColor=INK,
    leading=16, spaceBefore=12, spaceAfter=4)

S_H3 = style("WP_H3",
    fontName="Helvetica-BoldOblique", fontSize=10, textColor=MUTED,
    leading=14, spaceBefore=8, spaceAfter=3)

S_BODY = style("WP_Body",
    fontName="Helvetica", fontSize=9.5, textColor=INK,
    leading=15, spaceAfter=5, alignment=TA_JUSTIFY)

S_BULLET = style("WP_Bullet",
    fontName="Helvetica", fontSize=9.5, textColor=INK,
    leading=14, spaceAfter=2, leftIndent=14, bulletIndent=0)

S_CODE = style("WP_Code",
    fontName="Courier", fontSize=8.5, textColor=INK,
    leading=13, spaceAfter=2, leftIndent=10,
    backColor=SOFT)

S_CAPTION = style("WP_Caption",
    fontName="Helvetica-Oblique", fontSize=8, textColor=MUTED,
    leading=12, spaceAfter=4, alignment=TA_CENTER)

def hr():
    return HRFlowable(width="100%", thickness=0.5, color=LINE, spaceAfter=8, spaceBefore=4)

def h1(text):
    return [Spacer(1, 4), Paragraph(text, S_H1), hr()]

def h2(text):
    return [Paragraph(text, S_H2)]

def h3(text):
    return [Paragraph(text, S_H3)]

def p(text):
    return Paragraph(text, S_BODY)

def b(text):
    return Paragraph(f"• {text}", S_BULLET)

def code(text):
    return Paragraph(text, S_CODE)

def sp(n=6):
    return Spacer(1, n)

def table(data, col_widths, header=True):
    t = Table(data, colWidths=col_widths)
    style_cmds = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, SOFT]),
        ("GRID", (0, 0), (-1, -1), 0.3, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]
    if header:
        style_cmds += [
            ("BACKGROUND", (0, 0), (-1, 0), INK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ]
    t.setStyle(TableStyle(style_cmds))
    return t


def build():
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title="Astraios Technical Whitepaper",
        author="Astraios",
    )

    story = []

    # ── Cover ──────────────────────────────────────────────────────────────
    story += [
        Spacer(1, 30),
        Paragraph("ASTRAIOS", S_TITLE),
        Paragraph("Technical Whitepaper", S_SUB),
        Spacer(1, 6),
        HRFlowable(width="100%", thickness=2, color=ACCENT, spaceAfter=10),
        Paragraph("Quantitative ML Trading Platform · v1.0 · May 2026", S_META),
        Spacer(1, 6),
        Paragraph(
            "Astraios is a full-stack quantitative trading platform for cryptocurrency "
            "derivatives. It combines a Transformer-based signal engine, real-time Bybit "
            "integration for USDT perpetuals, and a React/FastAPI web application with "
            "per-user API key isolation, live/paper mode toggle, and a 1-second position "
            "update loop.",
            S_BODY,
        ),
        PageBreak(),
    ]

    # ── 1. System Architecture ─────────────────────────────────────────────
    story += h1("1. System Architecture")
    story += [
        p("Astraios follows a monorepo structure with a Python FastAPI backend, a React "
          "single-page application, a PostgreSQL database, and a separate ML pipeline "
          "for training on AWS SageMaker. The platform serves both an API and the built "
          "frontend from a single uvicorn process in production."),
        sp(),
    ]

    arch_data = [
        ["Layer", "Technology", "Role"],
        ["API Server", "FastAPI + Uvicorn", "REST endpoints, SPA serving, lifespan hooks"],
        ["Database", "PostgreSQL + asyncpg", "Users, signals, positions (async SQLAlchemy)"],
        ["Background Jobs", "asyncio tasks", "Signal refresh (15 min), price refresh (5 min)"],
        ["Market Data", "Bybit API + yfinance", "Klines, tickers, price feeds"],
        ["ML Engine", "PyTorch + SageMaker", "MarketTransformer training and inference"],
        ["Frontend", "React 19 + Vite", "SPA: dashboard, charts, trade terminal"],
        ["Charts", "lightweight-charts v4", "Candlestick + volume, 1s poll"],
        ["Auth", "JWT (python-jose)", "Per-user auth, 24h expiry"],
        ["Migrations", "Alembic", "Schema versioning"],
    ]
    story.append(table(arch_data, [38*mm, 50*mm, 80*mm]))
    story.append(sp(10))

    story += h2("1.1 Data Flow")
    story += [
        p("At startup, the lifespan hook creates all database tables and launches two "
          "background asyncio tasks. Signal generation runs every 15 minutes: it fetches "
          "the latest 100 candles per symbol from Bybit, engineers 25 features, runs the "
          "trained MarketTransformer, and writes one signal per ticker per user to "
          "PostgreSQL. Price refresh runs every 5 minutes via yfinance for any open paper "
          "positions. On the frontend, Bybit positions and wallet data poll the live API "
          "every 1 second; chart candles update every 5 seconds."),
        sp(8),
    ]

    # ── 2. ML Model ────────────────────────────────────────────────────────
    story += h1("2. MarketTransformer — Signal Engine")
    story += [
        p("The signal engine uses a Transformer encoder architecture trained to classify "
          "the forward 6-hour return of a cryptocurrency futures contract into three "
          "classes: BUY (>+1%), SELL (<−1%), or HOLD (±1%). The model was trained on "
          "AWS SageMaker and achieves 66.1% validation accuracy across 12 symbols — "
          "versus a 33% random baseline for a balanced 3-class problem."),
        sp(),
    ]

    story += h2("2.1 Architecture")
    arch_model = [
        ["Component", "Configuration"],
        ["Input projection", "Linear(25 → 128)"],
        ["Positional encoding", "Sinusoidal, max_len=512"],
        ["Encoder layers", "3 × TransformerEncoderLayer"],
        ["Attention heads", "4"],
        ["d_model", "128"],
        ["Feed-forward dim", "256"],
        ["Activation", "GELU"],
        ["Dropout", "0.1 (training), 0.0 (inference)"],
        ["Classification head", "Linear(128→256) → GELU → Dropout → Linear(256→3)"],
        ["Output", "3 logits → softmax probabilities"],
    ]
    story.append(table(arch_model, [65*mm, 100*mm]))
    story.append(sp(10))

    story += h2("2.2 Input Sequence")
    story += [
        p("The model operates on a sliding window of 32 consecutive 1-hour candles "
          "(32 hours of history). Each candle is represented as a 25-dimensional feature "
          "vector. The input tensor shape is (batch, 32, 25). The final encoder token "
          "(position −1) is passed to the classification head."),
        sp(8),
    ]

    # ── 3. Feature Engineering ─────────────────────────────────────────────
    story += h1("3. Feature Engineering")
    story += [
        p("All 25 features are computed from raw OHLCV kline data. Features are "
          "normalised using a StandardScaler fitted on the training corpus; the "
          "scaler mean and scale vectors are serialised into config.json alongside "
          "the model weights for consistent inference."),
        sp(),
    ]

    feat_data = [
        ["Feature", "Formula / Description", "Category"],
        ["returns", "pct_change(close)", "Return"],
        ["log_returns", "log(close / close[−1])", "Return"],
        ["ema_ratio_8", "close / EMA(close, 8)", "Trend"],
        ["ema_ratio_21", "close / EMA(close, 21)", "Trend"],
        ["ema_ratio_50", "close / EMA(close, 50)", "Trend"],
        ["ema_cross_8_21", "EMA(8) − EMA(21)", "Trend"],
        ["rsi_14", "RSI(14)", "Oscillator"],
        ["rsi_7", "RSI(7)", "Oscillator"],
        ["macd", "EMA(12) − EMA(26)", "Momentum"],
        ["macd_signal", "EMA(macd, 9)", "Momentum"],
        ["macd_hist", "macd − macd_signal", "Momentum"],
        ["bb_pct", "(close − BB_lower) / (BB_upper − BB_lower)", "Volatility"],
        ["atr_norm", "ATR(14) / close", "Volatility"],
        ["vol_ratio", "volume / MA(volume, 20)", "Volume"],
        ["ret_lag_1..5", "returns shifted 1, 2, 3, 5 bars", "Lag"],
        ["mom_5/10/20", "close / close[−N] − 1", "Momentum"],
        ["high_low_range", "(high − low) / close", "Range"],
        ["close_position", "(close − low) / (high − low)", "Range"],
        ["rolling_vol_5", "std(returns, 5)", "Volatility"],
        ["rolling_vol_20", "std(returns, 20)", "Volatility"],
    ]
    story.append(table(feat_data, [38*mm, 84*mm, 27*mm]))
    story.append(sp(10))

    # ── 4. Training Procedure ──────────────────────────────────────────────
    story += h1("4. Training Procedure")

    story += h2("4.1 Dataset")
    story += [
        p("Training data is collected via the Bybit linear kline endpoint. For each of "
          "11 symbols, 1,000 1-hour candles are fetched (paginated in batches of 200), "
          "features are engineered, and labels are generated from 6-bar forward returns. "
          "The final dataset contains 10,714 samples with the following class balance: "
          "SELL 2,108 (19.7%), HOLD 6,429 (60.0%), BUY 2,177 (20.3%)."),
        sp(),
    ]

    story += h2("4.2 Label Generation")
    story += [
        b("Forward horizon: 6 candles (6 hours on 1h chart)"),
        b("BUY (class 2): forward_return > +1%"),
        b("SELL (class 0): forward_return < −1%"),
        b("HOLD (class 1): −1% ≤ forward_return ≤ +1%"),
        sp(),
    ]

    story += h2("4.3 Training Configuration")
    train_data = [
        ["Hyperparameter", "Value"],
        ["Epochs", "50"],
        ["Batch size", "64"],
        ["Optimizer", "AdamW (lr=0.001, weight_decay=1e-4)"],
        ["LR schedule", "Cosine Annealing (T_max=50)"],
        ["Loss function", "CrossEntropyLoss with inverse-frequency class weights"],
        ["Gradient clipping", "1.0 (max norm)"],
        ["Train/val split", "80/20 per symbol (chronological, no leakage)"],
        ["Training platform", "AWS SageMaker ml.m5.xlarge (CPU)"],
        ["Best val accuracy", "66.1%"],
    ]
    story.append(table(train_data, [65*mm, 100*mm]))
    story.append(sp(10))

    story += h2("4.4 Class Weighting")
    story += [
        p("To address class imbalance (HOLD accounts for 60% of samples), class weights "
          "are computed as the inverse of class frequency, then normalised to sum to 3. "
          "This prevents the model from collapsing to always predicting HOLD."),
        sp(8),
    ]

    # ── 5. Inference Pipeline ──────────────────────────────────────────────
    story += h1("5. Inference Pipeline")
    story += [
        p("At signal generation time, the model singleton is loaded once into memory "
          "from ml/output/model.pt and ml/output/config.json. For each symbol, the "
          "following steps run synchronously inside asyncio.to_thread to avoid blocking "
          "the event loop:"),
        sp(),
        b("Fetch 100 most recent 1h candles from Bybit (proxied if US region)"),
        b("Extract close, high, low, volume arrays"),
        b("Engineer 25 features using the same pipeline as training"),
        b("Replace NaN/inf with 0, normalise with stored scaler parameters"),
        b("Slice the last 32 timesteps into the input sequence"),
        b("Forward pass → softmax → argmax for action, max probability for confidence"),
        b("Append RSI context (overbought/oversold) to rationale string"),
        b("Fall back to heuristic momentum scoring if model files are absent"),
        sp(8),
    ]

    # ── 6. API Reference ───────────────────────────────────────────────────
    story += h1("6. REST API Reference")

    story += h2("6.1 Authentication")
    story += [
        p("All endpoints except /api/health require a Bearer JWT token. Tokens are "
          "issued on POST /api/auth/register and POST /api/auth/login, expire after "
          "24 hours, and carry the user UUID as the subject claim."),
        sp(),
    ]

    story += h2("6.2 Trade Endpoints")
    trade_ep = [
        ["Method", "Path", "Description"],
        ["GET", "/api/trade/klines", "Kline data (up to 1,000 candles, paginated)"],
        ["GET", "/api/trade/symbols", "All USDT perp symbols sorted by 24h volume"],
        ["GET", "/api/trade/positions", "Open positions (live or testnet)"],
        ["GET", "/api/trade/wallet", "Account equity, available balance, PnL"],
        ["GET", "/api/trade/orders", "Open orders"],
        ["POST", "/api/trade/order", "Place market order with optional TP/SL"],
        ["POST", "/api/trade/close", "Close position with reverse market order"],
        ["POST", "/api/trade/leverage", "Set symbol leverage on Bybit"],
    ]
    story.append(table(trade_ep, [18*mm, 52*mm, 98*mm]))
    story.append(sp(8))

    story += h2("6.3 Signal Endpoints")
    signal_ep = [
        ["Method", "Path", "Description"],
        ["GET", "/api/signals", "Latest signal per USDT ticker, sorted by confidence DESC"],
        ["POST", "/api/signals", "Manually create a signal"],
        ["DELETE", "/api/signals/{id}", "Delete a signal"],
    ]
    story.append(table(signal_ep, [18*mm, 52*mm, 98*mm]))
    story.append(sp(8))

    story += h2("6.4 Account Endpoints")
    acct_ep = [
        ["Method", "Path", "Description"],
        ["GET", "/api/account/stats", "Portfolio metrics and key configuration status"],
        ["POST", "/api/account/api-keys", "Save mainnet Bybit API credentials"],
        ["DELETE", "/api/account/api-keys", "Remove mainnet credentials"],
        ["POST", "/api/account/testnet-keys", "Save testnet Bybit API credentials"],
        ["DELETE", "/api/account/testnet-keys", "Remove testnet credentials"],
    ]
    story.append(table(acct_ep, [18*mm, 62*mm, 88*mm]))
    story.append(sp(10))

    # ── 7. Bybit Integration ───────────────────────────────────────────────
    story += h1("7. Bybit Integration")
    story += [
        p("All Bybit calls use the pybit.unified_trading.HTTP client with the linear "
          "(USDT perpetual) category. Authentication is per-user: each API call resolves "
          "the user's stored mainnet or testnet credentials from PostgreSQL, falling back "
          "to server-level environment variables if present. An optional HTTP/HTTPS proxy "
          "is configured via BYBIT_PROXY in .env to route around regional IP restrictions."),
        sp(),
        b("Market orders only — no limit order support in this release"),
        b("GTC (Good Till Cancel) time-in-force for all orders"),
        b("Unified account mode required (supports cross-margin USDT perps)"),
        b("Kline pagination: 200 candles per request, looped to fetch up to 1,000"),
        sp(8),
    ]

    # ── 8. Data Models ─────────────────────────────────────────────────────
    story += h1("8. Database Schema")

    story += h2("8.1 Users")
    user_schema = [
        ["Column", "Type", "Notes"],
        ["id", "UUID", "Primary key, default uuid4"],
        ["email", "VARCHAR(320)", "Unique, indexed"],
        ["hashed_password", "VARCHAR(128)", "bcrypt"],
        ["name", "VARCHAR(120)", ""],
        ["plan", "VARCHAR(40)", "Default 'Private Beta'"],
        ["is_active", "BOOLEAN", "Default true"],
        ["created_at", "TIMESTAMPTZ", "UTC"],
        ["bybit_api_key", "VARCHAR(256)", "Nullable, mainnet"],
        ["bybit_api_secret", "VARCHAR(256)", "Nullable, mainnet"],
        ["bybit_testnet_key", "VARCHAR(256)", "Nullable, testnet"],
        ["bybit_testnet_secret", "VARCHAR(256)", "Nullable, testnet"],
    ]
    story.append(table(user_schema, [45*mm, 42*mm, 81*mm]))
    story.append(sp(8))

    story += h2("8.2 Signals")
    sig_schema = [
        ["Column", "Type", "Notes"],
        ["id", "UUID", "Primary key"],
        ["user_id", "UUID", "FK → users, indexed"],
        ["ticker", "VARCHAR(20)", "Indexed, USDT perp symbol"],
        ["action", "VARCHAR(10)", "'BUY', 'SELL', 'HOLD'"],
        ["confidence", "FLOAT", "[0.0, 1.0]"],
        ["rationale", "TEXT", "Nullable"],
        ["created_at", "TIMESTAMPTZ", "UTC"],
    ]
    story.append(table(sig_schema, [45*mm, 42*mm, 81*mm]))
    story.append(sp(8))

    story += h2("8.3 Positions")
    pos_schema = [
        ["Column", "Type", "Notes"],
        ["id", "UUID", "Primary key"],
        ["user_id", "UUID", "FK → users, indexed"],
        ["ticker", "VARCHAR(20)", "Indexed"],
        ["quantity", "FLOAT", ""],
        ["entry_price", "FLOAT", ""],
        ["current_price", "FLOAT", "Updated by price refresh job"],
        ["created_at", "TIMESTAMPTZ", "UTC"],
        ["updated_at", "TIMESTAMPTZ", "Auto-updated on write"],
    ]
    story.append(table(pos_schema, [45*mm, 42*mm, 81*mm]))
    story.append(sp(10))

    # ── 9. Scheduler ───────────────────────────────────────────────────────
    story += h1("9. Background Scheduler")
    story += [
        p("Two asyncio tasks are launched on application startup via the FastAPI "
          "lifespan context manager. Both tasks run inside an infinite loop with "
          "asyncio.sleep between iterations."),
        sp(),
    ]
    sched_data = [
        ["Task", "Interval", "Action"],
        ["refresh_signals", "Every 15 minutes", "Generate transformer signals for all users"],
        ["refresh_prices", "Every 5 minutes", "Update current_price on paper positions via yfinance"],
    ]
    story.append(table(sched_data, [45*mm, 35*mm, 88*mm]))
    story.append(sp(10))

    # ── 10. Security ───────────────────────────────────────────────────────
    story += h1("10. Security Model")
    story += [
        b("Passwords hashed with bcrypt (passlib)"),
        b("JWTs signed with HS256; secret rotatable via JWT_SECRET env var"),
        b("API keys stored in plaintext in PostgreSQL — encryption at rest recommended for production"),
        b("Each trade API call resolves credentials from the authenticated user's DB row — cross-user key access is impossible by design"),
        b("CORS configured for all origins in development; should be restricted to the frontend domain in production"),
        b(".env excluded from version control via .gitignore"),
        sp(10),
    ]

    # ── 11. ML Training on SageMaker ──────────────────────────────────────
    story += h1("11. AWS SageMaker Training Pipeline")
    story += [
        p("The ML pipeline is decoupled from the main application. Training is triggered "
          "manually via ml/launch_sagemaker.py, which packages the training script, "
          "uploads the dataset CSV to S3, and submits a SageMaker CreateTrainingJob "
          "request using the boto3 client directly (bypassing the SageMaker SDK to "
          "avoid version compatibility issues)."),
        sp(),
    ]
    sm_data = [
        ["Parameter", "Value"],
        ["Training image", "pytorch-training:2.1.0-cpu-py310-ubuntu20.04-sagemaker"],
        ["Instance type", "ml.m5.xlarge"],
        ["Max runtime", "3,600 seconds"],
        ["S3 bucket", "astraiosbucket"],
        ["Output path", "s3://astraiosbucket/ml/training/output/"],
        ["Model artifacts", "model.pt + config.json → model.tar.gz"],
    ]
    story.append(table(sm_data, [65*mm, 103*mm]))
    story.append(sp(10))

    # ── 12. Frontend ───────────────────────────────────────────────────────
    story += h1("12. Frontend Architecture")
    story += [
        p("The React SPA is built with Vite 6 and served directly from the FastAPI "
          "process via StaticFiles mounts. The application uses React Router for "
          "client-side routing across three views: landing (/), login (/login), and "
          "dashboard (/dashboard)."),
        sp(),
        b("React 19, React Router DOM, pure CSS (no UI framework)"),
        b("lightweight-charts v4 for candlestick charts with 1s live polling"),
        b("Trading mode (live/paper), selected symbol, and chart interval persisted in localStorage"),
        b("Bybit symbol selector fetches all 546 USDT perps from the API, searchable"),
        b("Dual render pattern: desktop table + mobile card stack for positions and signals"),
        b("Responsive breakpoints at 980px (tablet) and 640px (mobile)"),
        sp(10),
    ]

    # ── 13. Supported Symbols ─────────────────────────────────────────────
    story += h1("13. Supported Signal Symbols")
    story += [
        p("The signal engine covers 12 high-liquidity USDT perpetual futures on Bybit. "
          "Symbols were selected based on 24h turnover, market maturity, and data availability "
          "going back at least 1,000 hours."),
        sp(),
    ]
    sym_data = [
        ["Symbol", "Underlying", "Category"],
        ["BTCUSDT", "Bitcoin", "Layer 1"],
        ["ETHUSDT", "Ethereum", "Layer 1"],
        ["SOLUSDT", "Solana", "Layer 1"],
        ["SUIUSDT", "Sui", "Layer 1"],
        ["DOGEUSDT", "Dogecoin", "Meme"],
        ["XRPUSDT", "XRP", "Layer 1"],
        ["LINKUSDT", "Chainlink", "Oracle"],
        ["AAVEUSDT", "Aave", "DeFi"],
        ["AVAXUSDT", "Avalanche", "Layer 1"],
        ["ARBUSDT", "Arbitrum", "Layer 2"],
        ["WIFUSDT", "dogwifhat", "Meme"],
        ["1000PEPEUSDT", "PEPE ×1000", "Meme"],
    ]
    story.append(table(sym_data, [42*mm, 55*mm, 71*mm]))
    story.append(sp(10))

    # ── Closing ────────────────────────────────────────────────────────────
    story += [
        PageBreak(),
        HRFlowable(width="100%", thickness=2, color=ACCENT, spaceAfter=12),
        Paragraph("Astraios · Technical Whitepaper · v1.0 · May 2026", S_META),
        Spacer(1, 4),
        Paragraph(
            "This document describes the technical architecture of the Astraios platform "
            "as of May 2026. Astraios is a technology platform — not investment advice. "
            "Cryptocurrency derivatives trading carries significant risk of loss. Past "
            "signal accuracy does not guarantee future performance.",
            S_CAPTION,
        ),
    ]

    doc.build(story)
    print(f"PDF written to {OUTPUT}")


if __name__ == "__main__":
    build()
