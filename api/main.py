import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.config import settings
from api.db import engine, Base
from api.limiter import limiter
from api.models import User, Signal, Position, AutoTradeConfig, AutoTradeLog  # noqa: F401
from api.routes import auth, signals, portfolio, account, market, trade, auto_trade
from api.services import scheduler

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
)
log = logging.getLogger("astraios.main")

SITE_DIR = Path(__file__).resolve().parent.parent / "site"


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await scheduler.start()
    yield
    scheduler.stop()
    await engine.dispose()


app = FastAPI(
    title="Astraios API",
    description="Quantitative trading platform — signals, portfolio, and execution.",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.middleware("http")
async def request_logger(request: Request, call_next):
    req_id = str(uuid.uuid4())[:8]
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = round((time.monotonic() - start) * 1000)
    log.info(
        "req_id=%s method=%s path=%s status=%s duration_ms=%d",
        req_id, request.method, request.url.path, response.status_code, duration_ms,
    )
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.allowed_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(signals.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
app.include_router(account.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(trade.router, prefix="/api")
app.include_router(auto_trade.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if SITE_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=SITE_DIR / "assets"), name="assets")
    app.mount("/deck", StaticFiles(directory=SITE_DIR / "deck", html=True), name="deck")

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        file = SITE_DIR / full_path
        if file.is_file():
            return FileResponse(file)
        return FileResponse(SITE_DIR / "index.html")
