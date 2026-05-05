import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Float, Integer, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from api.db import Base


class AutoTradeConfig(Base):
    __tablename__ = "auto_trade_configs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    testnet: Mapped[bool] = mapped_column(Boolean, default=False)
    demo: Mapped[bool] = mapped_column(Boolean, default=True)

    # Execution venue: "bybit_demo" | "bybit_live" | "drift"
    execution_venue: Mapped[str] = mapped_column(String(20), default="bybit_demo")

    # Solana/Drift keys (Fernet-encrypted, stored only when venue=drift)
    solana_private_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    solana_rpc_url: Mapped[str | None] = mapped_column(String(256), nullable=True)

    confidence_threshold: Mapped[float] = mapped_column(Float, default=0.65)
    max_positions: Mapped[int] = mapped_column(Integer, default=3)
    position_size_pct: Mapped[float] = mapped_column(Float, default=5.0)
    leverage: Mapped[int] = mapped_column(Integer, default=1)
    tp_pct: Mapped[float] = mapped_column(Float, default=3.0)
    sl_pct: Mapped[float] = mapped_column(Float, default=1.5)
    daily_loss_limit: Mapped[float] = mapped_column(Float, default=50.0)

    symbols: Mapped[str] = mapped_column(Text, default="BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,DOGEUSDT,LTCUSDT,TRXUSDT,XRPUSDT")

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user: Mapped["User"] = relationship()


class AutoTradeLog(Base):
    __tablename__ = "auto_trade_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    qty: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="filled")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship()
