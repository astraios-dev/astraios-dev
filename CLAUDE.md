# Astraios — Quantitative ML Trading Platform

Full-stack crypto derivatives trading platform: ML signal engine → live Bybit USDT perps trading → React dashboard.

---

## Stack

| Layer | Tech |
|---|---|
| API | FastAPI + async SQLAlchemy + asyncpg + PostgreSQL |
| Auth | JWT (python-jose + bcrypt), per-user API key isolation |
| Frontend | React 19 + Vite 6 + pure CSS, SPA served by FastAPI |
| Market data | Bybit API (klines, OI, funding, L/S) + yfinance (paper positions) |
| ML | PyTorch MarketTransformer, trained on AWS SageMaker |
| Scheduler | asyncio background tasks (signals 15min, prices 5min) |
| Proxy | All Bybit/Binance calls routed through `http://45.3.45.91:3129` (US IP block) |

---

## How to run

```bash
# Start services
sudo systemctl start postgresql
source .venv/bin/activate
uvicorn api.main:app --host 127.0.0.1 --port 8000

# Build frontend
npm run build

# Retrain ML model
python ml/collect_data.py      # fetch dataset (~10min)
python ml/launch_sagemaker.py  # submit to SageMaker
```

---

## Project structure

```
astraios-dev/
├── api/
│   ├── main.py              # FastAPI app, lifespan, router mounts, SPA serving
│   ├── config.py            # pydantic-settings (.env: DATABASE_URL, JWT_SECRET, BYBIT_PROXY)
│   ├── db.py                # async SQLAlchemy engine + session
│   ├── models/              # User, Signal, Position
│   ├── routes/              # auth, signals, portfolio, account, market, trade
│   ├── schemas/             # Pydantic request/response models
│   └── services/
│       ├── auth.py          # JWT + bcrypt
│       ├── bybit.py         # Bybit SDK wrapper (mainnet + testnet, proxy support)
│       ├── market_data.py   # yfinance price fetcher for paper positions
│       ├── scheduler.py     # asyncio background jobs
│       ├── seed.py          # demo data on registration
│       ├── signal_engine.py # MarketTransformer inference + heuristic fallback
│       └── ml_model.py      # MarketTransformer architecture definition
├── app/src/
│   ├── Dashboard.jsx        # Main dashboard (chart, trade terminal, signals, positions)
│   ├── App.jsx              # Landing page
│   ├── Login.jsx            # Register/login
│   ├── AuthContext.jsx      # JWT auth context
│   ├── api.js               # Fetch wrapper with Bearer token
│   └── styles.css           # All styles — dark editorial, 980px + 640px breakpoints
├── ml/
│   ├── collect_data.py      # Binance klines + Bybit OI/funding/L/S → dataset.csv
│   ├── train.py             # SageMaker training entry point
│   ├── model.py             # MarketTransformer architecture (mirrors ml_model.py)
│   ├── launch_sagemaker.py  # boto3 SageMaker job launcher
│   ├── dataset.csv          # 643K samples, 19 symbols, 35 features
│   └── output/
│       ├── model.pt         # Trained model weights
│       └── config.json      # Model config + scaler params + best_val_acc
├── alembic/                 # DB migrations (users, signals, positions, bybit keys)
├── docs/
│   └── astraios-whitepaper.pdf
├── site/                    # Built frontend (served by FastAPI)
├── .env                     # Secrets — NOT committed
└── requirements.txt
```

---

## Database schema

**Users**: id, email, hashed_password, name, plan, is_active, bybit_api_key, bybit_api_secret, bybit_testnet_key, bybit_testnet_secret

**Signals**: id, user_id, ticker (USDT perps only), action (BUY/SELL/HOLD), confidence, rationale, created_at

**Positions**: id, user_id, ticker, quantity, entry_price, current_price, created_at, updated_at

Migrations: `alembic upgrade head`

---

## Key API routes

```
POST /api/auth/register|login    JWT auth
GET  /api/signals                Latest signal per USDT ticker, sorted by confidence DESC
GET  /api/market/prices          Live prices via yfinance
POST /api/market/refresh         Trigger signal generation + price refresh
GET  /api/trade/klines           Bybit klines (up to 1000 candles, paginated)
GET  /api/trade/symbols          All 546 USDT perps sorted by 24h volume
GET  /api/trade/positions        Live Bybit positions (?testnet=true for paper)
GET  /api/trade/wallet           Bybit wallet (equity, available, PnL)
POST /api/trade/order            Market order (symbol, side, qty, tp?, sl?, testnet?)
POST /api/trade/close            Close position (reverse market order)
POST /api/trade/leverage         Set leverage for symbol
GET  /api/account/stats          Portfolio metrics + API key status
POST /api/account/api-keys       Save mainnet Bybit keys
POST /api/account/testnet-keys   Save testnet Bybit keys
```

---

## Dashboard features

- **Live/Paper toggle** — Live hits Bybit mainnet, Paper hits Bybit testnet. Persisted in localStorage.
- **Trade terminal** — Symbol selector (546 perps, searchable), candlestick chart (lightweight-charts v4), Long/Short side toggle, leverage selector (1–100x), quick-size buttons (10/25/50/100% of balance), TP/SL inputs. Chart polls every 5s. Positions poll every 1s.
- **Top trades** — Page 1 shows top 10 signals by confidence, ranked. Signals deduplicated per ticker (latest only). USDT perps only.
- **Keys prompt** — Shows setup prompt instead of trade UI when no API keys configured for current mode.
- **Mobile** — Signal cards, position cards, bottom-sheet symbol selector, 3-col market strip at 640px.

---

## ML signal engine

**Model**: MarketTransformer — 3-layer Transformer encoder, d_model=128, 4 heads, seq_len=48 1h bars, 35 features, pre-norm + Xavier init.

**Features (35)**: returns, log_returns, EMA ratios (8/21/50), EMA cross, RSI (7/14), MACD (line/signal/hist), Bollinger %B, ATR norm, volume ratio, return lags (1/2/3/5), momentum (5/10/20), high-low range, close position, rolling vol (5/20), funding rate (+ ma8/std8/cumulative), OI change/ratio/divergence, long-short ratio (+ ma8/change).

**Labels**: Triple barrier — +1.5×ATR upper, −1.0×ATR lower, 12-bar timeout. BUY=2, HOLD=1, SELL=0.

**Training data**: 643K samples, 19 symbols (Binance futures klines, 5+ years where available). Binance for OHLCV + funding. Bybit for OI + L/S ratio (recent ~500 bars, NaN-filled with neutral for historical rows).

**Training**: SageMaker `ml.g5.xlarge` (NVIDIA A10G). lr=5e-5, CosineAnnealingLR, batch=256, 60 epochs, ±5σ feature clipping, walk-forward 80/20 split per symbol. Best val acc so far: ~35-40%.

**Inference**: `api/services/signal_engine.py` loads `ml/output/model.pt` + `config.json` on startup. Fetches 200 1h candles + funding/OI/LS from Bybit per symbol, engineers features, scales with saved scaler, runs model. Falls back to heuristic momentum if model not found.

**To retrain**:
```bash
python ml/collect_data.py   # ~10min, saves ml/dataset.csv
python ml/launch_sagemaker.py  # submits job, downloads output to ml/output/
# Then restart uvicorn — model loads automatically
```

---

## AWS setup

- **Account**: 125499242423
- **Region**: us-east-1
- **Role**: astrax (EC2 instance role)
- **S3 bucket**: astraiosbucket (training data + model artifacts)
- **SageMaker**: GPU quotas approved — ml.g5.xlarge, ml.g4dn.xlarge. p5 quota requests pending.
- **Proxy**: Bybit + Binance blocked from US IP — all calls use `BYBIT_PROXY=http://45.3.45.91:3129`

---

## .env variables

```
DATABASE_URL=postgresql+asyncpg://astraios:astraios_dev_2026@localhost:5432/astraios
JWT_SECRET=<secret>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
BYBIT_API_KEY=          # empty — keys stored per-user in DB
BYBIT_API_SECRET=       # empty — keys stored per-user in DB
BYBIT_PROXY=http://45.3.45.91:3129
```

---

## Design language

Dark editorial: `--paper: #050505`, `--ink: #fff`, `--soft: #141414`, `--line: #2a2a2a`, `--muted: #9a9a97`. Georgia serif for headings/numbers. Uppercase 0.7rem 800-weight labels. 1px `var(--line)` borders everywhere. Green `#2ecb71` / Red `#e04040` for directional values. No UI framework — pure CSS.

---

## Current state (as of May 2026)

- Full trading platform functional end-to-end
- Bybit mainnet/testnet integration with per-user API keys
- MarketTransformer training on 643K samples currently running on ml.g5.xlarge
- Signal engine running (falls back to heuristic until new model downloads)
- Dashboard: live charts, trade terminal, mobile-optimised
- Whitepaper at docs/astraios-whitepaper.pdf
- GitHub: github.com/astraios-dev/astraios-dev (main branch)
