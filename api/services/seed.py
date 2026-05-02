from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from api.models.signal import Signal
from api.models.position import Position

SEED_SIGNALS = [
    {"ticker": "AAPL", "action": "BUY", "confidence": 0.87, "rationale": "Regime shift to bullish; TFT forecast +3.2% over 5d horizon. Insider buying cluster in EDGAR filings."},
    {"ticker": "SOL/USD", "action": "HOLD", "confidence": 0.72, "rationale": "Neutral regime. Momentum fading but macro overlay still supportive. Wait for confirmation."},
    {"ticker": "MSFT", "action": "SELL", "confidence": 0.81, "rationale": "Earnings miss probability elevated. HMM regime risk-off. Position exceeds Kelly threshold."},
    {"ticker": "ETH/USD", "action": "BUY", "confidence": 0.65, "rationale": "On-chain volume spike. LSTM sequence pattern matches prior breakout setups. Lower confidence — size accordingly."},
    {"ticker": "NVDA", "action": "HOLD", "confidence": 0.59, "rationale": "Conflicting signals across model ensemble. High IV regime. No edge — stay flat."},
]

SEED_POSITIONS = [
    {"ticker": "AAPL", "quantity": 45, "entry_price": 189.20, "current_price": 194.55},
    {"ticker": "SOL/USD", "quantity": 120, "entry_price": 142.80, "current_price": 145.10},
    {"ticker": "MSFT", "quantity": 20, "entry_price": 421.50, "current_price": 418.30},
    {"ticker": "GOOGL", "quantity": 30, "entry_price": 172.40, "current_price": 175.80},
    {"ticker": "ETH/USD", "quantity": 2.5, "entry_price": 3280.00, "current_price": 3310.40},
    {"ticker": "AMZN", "quantity": 15, "entry_price": 186.20, "current_price": 184.90},
]


async def seed_user_data(user_id: UUID, db: AsyncSession):
    for s in SEED_SIGNALS:
        db.add(Signal(user_id=user_id, **s))
    for p in SEED_POSITIONS:
        db.add(Position(user_id=user_id, **p))
    await db.commit()
