This is Astraios — a quantitative ML trading platform for retail and semi-pro traders. It's a monorepo with a React frontend and FastAPI backend.

## What it does
Surfaces ranked market signals (BUY/SELL/HOLD) with confidence scores and rationale, plus a paper-first auto-trading API. Users register, get seeded demo data (5 signals, 6 positions), and see a live dashboard pulling from the API.

## Stack

**Frontend** (app/)
- React 19 + React Router DOM (SPA with client-side routing)
- Vite 6 (dev server proxies /api → localhost:8000)
- Pure CSS (no framework) — dark editorial design, responsive down to mobile
- Key files: App.jsx (landing page), Login.jsx (register/login toggle), Dashboard.jsx (live data from API), AuthContext.jsx (JWT auth context), api.js (fetch wrapper)

**Backend** (api/)
- FastAPI with async SQLAlchemy + asyncpg
- PostgreSQL (database: astraios, user: astraios)
- JWT auth (python-jose + bcrypt) — register, login, /auth/me
- Alembic migrations (one initial migration: users, signals, positions tables)
- Routes: /api/auth/*, /api/signals, /api/portfolio, /api/account/stats, /api/health
- Models: User, Signal (BUY/SELL/HOLD + confidence + rationale), Position (with computed P&L)
- Seed service auto-populates demo signals + positions on user registration

**Infra**
- Python 3.12 venv at .venv/
- PostgreSQL runs locally (systemctl)
- Production: `uvicorn api.main:app` on :8000 serves both API and built SPA from site/
- Dev: `npm run dev` on :5173 with Vite proxy to :8000

## Project structure
```
astraios-dev/
├── api/                    # FastAPI backend
│   ├── main.py             # App factory, CORS, SPA serving, router mounts
│   ├── config.py           # pydantic-settings from .env
│   ├── db.py               # Async SQLAlchemy engine + session
│   ├── models/             # User, Signal, Position (SQLAlchemy)
│   ├── routes/             # auth, signals, portfolio, account
│   ├── schemas/            # Pydantic request/response models
│   └── services/           # auth (JWT + bcrypt), seed (demo data)
├── app/                    # React frontend (Vite root)
│   ├── src/
│   │   ├── App.jsx         # Landing page with nav, hero, sections
│   │   ├── Login.jsx       # Login/register form
│   │   ├── Dashboard.jsx   # Live dashboard (signals table, positions, stats)
│   │   ├── AuthContext.jsx  # JWT auth provider
│   │   ├── api.js          # API client (fetch + Bearer token)
│   │   ├── main.jsx        # Router setup (/, /login, /dashboard)
│   │   └── styles.css      # All styles (dark theme, responsive, mobile cards)
│   └── index.html
├── alembic/                # Database migrations
├── site/                   # Built frontend output (served by FastAPI)
├── public/                 # Static assets (logos, favicon, deck)
├── .env                    # DATABASE_URL, JWT_SECRET, JWT_ALGORITHM
├── vite.config.js
└── package.json
```

## How to run
```bash
# Backend
sudo systemctl start postgresql
source .venv/bin/activate
alembic upgrade head
uvicorn api.main:app --host 127.0.0.1 --port 8000

# Frontend dev
npm run dev

# Build frontend for production
npm run build
```

## Current state
- Landing page, login/register, and dashboard are all functional
- Backend serves all API endpoints + production SPA
- Auth flow: register → auto-seed → JWT → dashboard with live data
- Dashboard has signals table, positions table, portfolio stats, account info
- Mobile responsive: tables convert to card layouts at 640px
- No tests yet, no CI, no Docker
