"""
Intelligence Services — Advisory Layer

Ported from legacy Trade Bot intelligence subsystem.
All services in this package are ADVISORY ONLY:
  - They inform trading decisions but NEVER bypass Guardian, HITL, or execution controls.
  - All financial math uses Python Decimal — no float permitted.
  - All services use the new bot's database session factory.
  - An intelligence service failure MUST NOT crash the trading pipeline.
"""
