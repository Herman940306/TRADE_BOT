"""Phase 1 HITL test: creates a pending approval directly via HITLGateway + DB."""
import sys

sys.path.insert(0, "/app")
from decimal import Decimal
import os
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.hitl_config import get_hitl_config
from services.hitl_gateway import HITLGateway

# Connect to DB
db_url = os.getenv("DATABASE_URL", "postgresql://app_trading:trading_app_2024@db:5432/autonomous_alpha")
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)
db_session = Session()

config = get_hitl_config(validate=False)
gateway = HITLGateway(config=config, db_session=db_session)

result = gateway.create_approval_request(
    trade_id=uuid.uuid4(),
    instrument="BTCZAR",
    side="BUY",
    risk_pct=Decimal("0.0250"),
    confidence=Decimal("0.8500"),
    request_price=Decimal("1250000.50"),
    reasoning_summary={
        "bull_reasoning": "Phase 1 test signal - bullish engulfing pattern",
        "bear_reasoning": "N/A - test scenario",
        "consensus_score": 85,
        "final_verdict": True,
    },
    correlation_id=uuid.uuid4(),
)

if result.success and result.approval_request:
    pass
else:
    pass

db_session.close()
