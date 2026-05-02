from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.db import engine, Base
from api.models import User, Signal, Position  # noqa: F401
from api.routes import auth, signals, portfolio, account, market, trade
from api.services import scheduler

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
