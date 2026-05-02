from datetime import datetime
from pydantic import BaseModel, Field


class SignalCreate(BaseModel):
    ticker: str
    action: str = Field(pattern="^(BUY|SELL|HOLD)$")
    confidence: float = Field(ge=0, le=1)
    rationale: str | None = None


class SignalResponse(BaseModel):
    id: str
    ticker: str
    action: str
    confidence: float
    rationale: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
