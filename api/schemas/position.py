from datetime import datetime
from pydantic import BaseModel, Field


class PositionCreate(BaseModel):
    ticker: str
    quantity: float = Field(gt=0)
    entry_price: float = Field(gt=0)
    current_price: float = Field(gt=0)


class PositionUpdate(BaseModel):
    quantity: float | None = Field(default=None, gt=0)
    current_price: float | None = Field(default=None, gt=0)


class PositionResponse(BaseModel):
    id: str
    ticker: str
    quantity: float
    entry_price: float
    current_price: float
    pnl: float
    pnl_pct: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
