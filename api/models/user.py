import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from api.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    plan: Mapped[str] = mapped_column(String(40), default="Private Beta")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    bybit_api_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    bybit_api_secret: Mapped[str | None] = mapped_column(String(256), nullable=True)
    bybit_testnet_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    bybit_testnet_secret: Mapped[str | None] = mapped_column(String(256), nullable=True)

    signals: Mapped[list["Signal"]] = relationship(back_populates="user", lazy="selectin")
    positions: Mapped[list["Position"]] = relationship(back_populates="user", lazy="selectin")
