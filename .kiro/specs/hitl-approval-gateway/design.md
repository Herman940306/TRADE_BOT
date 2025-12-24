# HITL Approval Gateway - Design Document

## Overview

The HITL (Human-In-The-Loop) Approval Gateway is the central control mechanism ensuring no trade executes without explicit human authorization. It implements a hard gate with fail-closed semantics, timeout-to-reject behavior, and full forensic auditability.

### Prime Directive
> "The bot thinks. You approve. The system never betrays you."

### Execution Flow
```
Bot generates signal → Bot reasons (MCP) → Guardian check → Policy check → HITL approval → Trade executes
```

### Key Characteristics
- **Fail-Closed**: Any ambiguity results in REJECT
- **Guardian-First**: Capital protection always wins
- **Immutable Audit**: Every action is logged, hashed, and reconstructable
- **Timeout-to-Reject**: No response = REJECT (never auto-approve)

## Architecture

```mermaid
flowchart TB
    subgraph Signal Generation
        STR[Strategies] --> TLM[Trade Lifecycle Manager]
    end
    
    subgraph HITL Gateway
        TLM --> GC[Guardian Check]
        GC -->|UNLOCKED| ARC[Approval Request Creator]
        GC -->|LOCKED| BLOCK[Block with SEC-020]
        ARC --> DB[(hitl_approvals)]
        ARC --> WS[WebSocket Emitter]
        ARC --> DC[Discord Notifier]
    end
    
    subgraph Decision Channels
        WS --> WEB[Web Command Hub]
        DC --> DISC[Discord Bot]
        WEB --> ADP[Approval Decision Processor]
        DISC --> ADP
    end
    
    subgraph Execution
        ADP -->|APPROVED| EXE[Exchange Executor]
        ADP -->|REJECTED| LOG[Audit Logger]
    end
    
    subgraph Background Jobs
        EXP[Expiry Worker] -->|every 30s| DB
        EXP -->|expired| ADP
    end
```

### Trade Lifecycle State Machine

```mermaid
stateDiagram-v2
    [*] --> PENDING: Signal generated
    PENDING --> AWAITING_APPROVAL: HITL request created
    AWAITING_APPROVAL --> ACCEPTED: Operator approves
    AWAITING_APPROVAL --> REJECTED: Operator rejects
    AWAITING_APPROVAL --> REJECTED: Timeout (HITL_TIMEOUT)
    AWAITING_APPROVAL --> REJECTED: Guardian lock (GUARDIAN_LOCK)
    AWAITING_APPROVAL --> REJECTED: Slippage exceeded (SEC-050)
    ACCEPTED --> FILLED: Order placed
    FILLED --> CLOSED: Position closed
    CLOSED --> SETTLED: Final reconciliation
    REJECTED --> [*]
    SETTLED --> [*]
```

### Valid State Transitions

```python
VALID_TRANSITIONS: Dict[str, List[str]] = {
    "PENDING": ["AWAITING_APPROVAL"],
    "AWAITING_APPROVAL": ["ACCEPTED", "REJECTED"],
    "ACCEPTED": ["FILLED"],
    "FILLED": ["CLOSED"],
    "CLOSED": ["SETTLED"],
}
```

## Components and Interfaces

### 1. HITLGateway (Core Service)

```python
from typing import Optional, List
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime
import uuid

@dataclass
class ApprovalRequest:
    """Immutable approval request record."""
    id: uuid.UUID
    trade_id: uuid.UUID
    instrument: str
    side: str  # BUY | SELL
    risk_pct: Decimal
    confidence: Decimal
    request_price: Decimal
    reasoning_summary: dict
    correlation_id: uuid.UUID
    status: str  # AWAITING_APPROVAL | APPROVED | REJECTED
    requested_at: datetime
    expires_at: datetime
    decided_at: Optional[datetime]
    decided_by: Optional[str]
    decision_channel: Optional[str]  # WEB | DISCORD | CLI | SYSTEM
    decision_reason: Optional[str]
    row_hash: str  # SHA-256

@dataclass
class ApprovalDecision:
    """Decision payload from operator."""
    trade_id: uuid.UUID
    decision: str  # APPROVE | REJECT
    operator_id: str
    channel: str  # WEB | DISCORD | CLI
    reason: Optional[str]
    comment: Optional[str]
    correlation_id: uuid.UUID

class HITLGateway:
    """Core HITL Gateway service."""
    
    def create_approval_request(
        self,
        trade_id: uuid.UUID,
        instrument: str,
        side: str,
        risk_pct: Decimal,
        confidence: Decimal,
        request_price: Decimal,
        reasoning_summary: dict,
        correlation_id: uuid.UUID
    ) -> ApprovalRequest:
        """Create new approval request. Checks Guardian first."""
        pass
    
    def process_decision(
        self,
        decision: ApprovalDecision
    ) -> ApprovalRequest:
        """Process operator decision. Re-checks Guardian and slippage."""
        pass
    
    def get_pending_approvals(self) -> List[ApprovalRequest]:
        """Get all pending approvals ordered by expires_at."""
        pass
    
    def recover_on_startup(self) -> None:
        """Recover pending approvals after restart."""
        pass
```

### 2. GuardianIntegration

```python
class GuardianIntegration:
    """Interface to Guardian service."""
    
    def is_locked(self) -> bool:
        """Check if Guardian is currently locked."""
        pass
    
    def get_status(self) -> dict:
        """Get full Guardian status including lock reason."""
        pass
    
    def on_lock_event(self, callback: Callable) -> None:
        """Register callback for Guardian lock events."""
        pass
```

### 3. SlippageGuard

```python
class SlippageGuard:
    """Price drift validation."""
    
    def __init__(self, max_slippage_pct: Decimal):
        self.max_slippage_pct = max_slippage_pct
    
    def validate(
        self,
        request_price: Decimal,
        current_price: Decimal
    ) -> tuple[bool, Decimal]:
        """
        Validate price drift.
        Returns (is_valid, deviation_pct).
        """
        pass
```

### 4. ExpiryWorker

```python
class ExpiryWorker:
    """Background job for timeout processing."""
    
    def __init__(self, interval_seconds: int = 30):
        self.interval_seconds = interval_seconds
    
    def run(self) -> None:
        """Main worker loop."""
        pass
    
    def process_expired(self) -> int:
        """Process all expired requests. Returns count."""
        pass
```

### 5. RowHasher

```python
class RowHasher:
    """SHA-256 integrity verification."""
    
    @staticmethod
    def compute(record: ApprovalRequest) -> str:
        """Compute SHA-256 hash of record fields."""
        pass
    
    @staticmethod
    def verify(record: ApprovalRequest) -> bool:
        """Verify stored hash matches computed hash."""
        pass
```

### 6. API Endpoints

```python
# FastAPI router for HITL endpoints

@router.get("/api/hitl/pending")
async def get_pending_approvals(
    current_user: User = Depends(get_current_user)
) -> List[PendingApprovalResponse]:
    """Get all pending approval requests."""
    pass

@router.post("/api/hitl/{trade_id}/approve")
async def approve_trade(
    trade_id: uuid.UUID,
    body: ApproveRequest,
    current_user: User = Depends(get_current_user)
) -> ApprovalResponse:
    """Approve a pending trade."""
    pass

@router.post("/api/hitl/{trade_id}/reject")
async def reject_trade(
    trade_id: uuid.UUID,
    body: RejectRequest,
    current_user: User = Depends(get_current_user)
) -> ApprovalResponse:
    """Reject a pending trade."""
    pass
```

## Data Models

### Database Schema

#### hitl_approvals (Crown Jewel Table)

```sql
CREATE TABLE hitl_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_id UUID NOT NULL,
    instrument VARCHAR(20) NOT NULL,
    side VARCHAR(4) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    risk_pct DECIMAL(5,2) NOT NULL,
    confidence DECIMAL(3,2) NOT NULL,
    request_price DECIMAL(18,8) NOT NULL,
    reasoning_summary JSONB NOT NULL,
    correlation_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN (
        'AWAITING_APPROVAL', 'APPROVED', 'REJECTED'
    )),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    decided_at TIMESTAMPTZ,
    decided_by VARCHAR(100),
    decision_channel VARCHAR(10) CHECK (decision_channel IN (
        'WEB', 'DISCORD', 'CLI', 'SYSTEM'
    )),
    decision_reason VARCHAR(500),
    row_hash CHAR(64) NOT NULL,
    
    CONSTRAINT fk_trade FOREIGN KEY (trade_id) 
        REFERENCES trades(id) ON DELETE RESTRICT
);

CREATE INDEX idx_hitl_pending ON hitl_approvals (status, expires_at)
    WHERE status = 'AWAITING_APPROVAL';
CREATE INDEX idx_hitl_correlation ON hitl_approvals (correlation_id);
CREATE INDEX idx_hitl_trade ON hitl_approvals (trade_id);
```

#### post_trade_snapshots

```sql
CREATE TABLE post_trade_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    approval_id UUID NOT NULL REFERENCES hitl_approvals(id),
    bid DECIMAL(18,8) NOT NULL,
    ask DECIMAL(18,8) NOT NULL,
    spread DECIMAL(18,8) NOT NULL,
    mid_price DECIMAL(18,8) NOT NULL,
    response_latency_ms INTEGER NOT NULL,
    price_deviation_pct DECIMAL(5,4) NOT NULL,
    correlation_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_snapshot_approval ON post_trade_snapshots (approval_id);
CREATE INDEX idx_snapshot_correlation ON post_trade_snapshots (correlation_id);
```

#### audit_log

```sql
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL,
    target_type VARCHAR(50) NOT NULL,
    target_id UUID,
    previous_state JSONB,
    new_state JSONB,
    payload JSONB,
    correlation_id UUID NOT NULL,
    error_code VARCHAR(10),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_correlation ON audit_log (correlation_id);
CREATE INDEX idx_audit_target ON audit_log (target_type, target_id);
CREATE INDEX idx_audit_action ON audit_log (action, created_at);
```

#### deep_link_tokens

```sql
CREATE TABLE deep_link_tokens (
    token VARCHAR(64) PRIMARY KEY,
    trade_id UUID NOT NULL REFERENCES hitl_approvals(trade_id),
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    correlation_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_token_expires ON deep_link_tokens (expires_at)
    WHERE used_at IS NULL;
```

### API Schemas

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal
from datetime import datetime
import uuid

class ReasoningSummary(BaseModel):
    trend: str
    volatility: str
    signal_confluence: List[str]
    notes: Optional[str]

class PendingApprovalResponse(BaseModel):
    trade_id: uuid.UUID
    instrument: str
    side: str
    risk_pct: Decimal = Field(decimal_places=2)
    confidence: Decimal = Field(decimal_places=2)
    request_price: Decimal = Field(decimal_places=8)
    expires_at: datetime
    seconds_remaining: int
    reasoning_summary: ReasoningSummary
    correlation_id: uuid.UUID

class ApproveRequest(BaseModel):
    approved_by: str
    channel: str = "WEB"
    comment: Optional[str]

class RejectRequest(BaseModel):
    rejected_by: str
    channel: str = "WEB"
    reason: str

class ApprovalResponse(BaseModel):
    status: str
    trade_id: uuid.UUID
    decided_at: datetime
    correlation_id: uuid.UUID
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

Based on the prework analysis, the following correctness properties have been identified:

### Property 1: Valid State Transitions Preserve Lifecycle Integrity

*For any* trade in any valid state, applying a valid transition SHALL result in the expected target state, and the original state SHALL be recorded in the audit log.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4**

### Property 2: Invalid State Transitions Are Rejected

*For any* trade in any state, attempting an invalid transition (not in VALID_TRANSITIONS map) SHALL leave the trade in its original state and log error code SEC-030.

**Validates: Requirements 1.5**

### Property 3: Guardian Lock Blocks All HITL Operations

*For any* HITL operation (create request or process decision), if Guardian status is LOCKED, the operation SHALL be rejected with error code SEC-020 and the blocked_by_guardian counter SHALL increment.

**Validates: Requirements 2.4, 2.5, 3.3, 11.1, 11.2, 11.3, 11.4, 11.5**

### Property 4: Row Hash Round-Trip Integrity

*For any* approval record, computing the SHA-256 hash of its fields and storing it, then later recomputing the hash, SHALL produce identical values. If values differ, error code SEC-080 SHALL be logged.

**Validates: Requirements 2.3, 5.2, 5.3, 6.1, 6.2, 6.3**

### Property 5: Unauthorized Operators Are Rejected

*For any* approval decision submitted by an operator not in HITL_ALLOWED_OPERATORS, the decision SHALL be rejected with error code SEC-090 and the unauthorized attempt SHALL be logged.

**Validates: Requirements 3.1, 3.2, 7.5, 7.6, 8.4**

### Property 6: Slippage Exceeding Threshold Causes Rejection

*For any* approval where the absolute price deviation between request_price and current_price exceeds HITL_SLIPPAGE_MAX_PERCENT, the approval SHALL be rejected with error code SEC-050.

**Validates: Requirements 3.5, 3.6**

### Property 7: Expired Requests Are Auto-Rejected

*For any* approval request where expires_at is less than current_time, the expiry worker SHALL transition status to REJECTED with decision_reason HITL_TIMEOUT and decision_channel SYSTEM.

**Validates: Requirements 1.4, 4.1, 4.2, 4.3**

### Property 8: Price Fields Maintain DECIMAL(18,8) Precision

*For any* price value written to hitl_approvals or post_trade_snapshots, the value SHALL be stored with DECIMAL(18,8) precision using ROUND_HALF_EVEN rounding, and reading the value SHALL return the exact stored value.

**Validates: Requirements 6.5, 12.5**

### Property 9: Operations Increment Correct Prometheus Counters

*For any* HITL operation (request creation, approval, rejection, timeout), the corresponding Prometheus counter SHALL increment by exactly 1, and rejection counters SHALL include the correct reason label.

**Validates: Requirements 9.1, 9.2, 9.3, 9.4, 4.6, 11.5**

### Property 10: All Decisions Create Complete Audit Records

*For any* state transition or decision, an audit_log entry SHALL be created containing actor_id, action, target_id, previous_state, new_state, and correlation_id.

**Validates: Requirements 1.6, 3.7, 3.8**

### Property 11: Approval Records Are Immutable (No Hard Deletes)

*For any* attempt to delete a record from hitl_approvals, the operation SHALL fail and the record SHALL remain in the database.

**Validates: Requirements 6.4**

### Property 12: Deep Link Tokens Are Single-Use

*For any* deep link token, after it has been used once (used_at is set), subsequent validation attempts SHALL fail.

**Validates: Requirements 8.5**

### Property 13: Post-Trade Snapshot Captures Complete Market Context

*For any* approved trade, a post_trade_snapshot SHALL be created containing bid, ask, spread, mid_price, response_latency_ms, price_deviation_pct, and correlation_id linking to the approval record.

**Validates: Requirements 12.1, 12.2, 12.3, 12.4**

### Property 14: Pending Approvals Are Ordered By Expiry

*For any* call to GET /api/hitl/pending, the returned list SHALL be ordered by expires_at ascending (soonest expiry first).

**Validates: Requirements 7.1**

### Property 15: HITL Disabled Mode Auto-Approves

*For any* approval request when HITL_ENABLED is false, the request SHALL be immediately approved with decision_reason HITL_DISABLED and decision_channel SYSTEM.

**Validates: Requirements 10.5**

## Error Handling

### Sovereign Error Codes

| Code | Category | Trigger | Action |
|------|----------|---------|--------|
| SEC-001 | Authentication | Missing/invalid auth token | Return 401, halt |
| SEC-002 | Token Invalid | Expired/malformed JWT | Return 401, halt |
| SEC-010 | Data Validation | Invalid request payload | Return 400, reject |
| SEC-020 | Guardian Lock | Guardian is LOCKED | Reject operation, notify |
| SEC-030 | State Invalid | Invalid state transition | Reject, maintain state |
| SEC-040 | Config Missing | Required env var missing | Fail startup |
| SEC-050 | Price Stale | Slippage exceeds threshold | Reject approval, notify |
| SEC-060 | HITL Timeout | Approval expired | Auto-reject |
| SEC-070 | Circuit Breaker | System overload | Enter neutral state |
| SEC-080 | Hash Mismatch | Row hash verification failed | Security alert, halt |
| SEC-090 | Unauthorized | Operator not in whitelist | Reject, log attempt |

### Error Response Format

```python
@dataclass
class ErrorResponse:
    error_code: str  # SEC-XXX
    message: str
    correlation_id: uuid.UUID
    timestamp: datetime
    details: Optional[dict]
```

### Fail-Closed Behavior

All error conditions default to REJECT or HALT:

```python
def handle_error(error_code: str, context: dict) -> None:
    """
    Fail-closed error handler.
    
    - SEC-001, SEC-002, SEC-040, SEC-080: HALT
    - SEC-010, SEC-020, SEC-030, SEC-050, SEC-060, SEC-090: REJECT
    - SEC-070: NEUTRAL_STATE
    """
    pass
```

## Core Services (Authoritative)

These are non-negotiable services. Every requirement maps to one or more of these.

| Service | Responsibility |
|---------|----------------|
| `hitl-gateway` | Approval lifecycle, expiry, slippage guard |
| `trade-lifecycle` | State machine enforcement |
| `guardian-service` | Capital lock / unlock |
| `auth-service` | JWT, roles, sessions |
| `discord-bridge` | Buttons, embeds, deep links |
| `websocket-hub` | Real-time updates |
| `audit-log-service` | Immutable audit trail |
| `market-data-service` | Price fetch + spreads |
| `background-jobs` | HITL expiry + recovery |

## Database Migrations (Ready to Paste)

### 1. trade_state ENUM (Required)

```sql
ALTER TYPE trade_state ADD VALUE IF NOT EXISTS 'AWAITING_APPROVAL';
```

### 2. trades (Extension)

```sql
ALTER TABLE trades 
ADD COLUMN correlation_id UUID NOT NULL,
ADD COLUMN last_state_change_at TIMESTAMP NOT NULL DEFAULT now();
```

### 3. hitl_approvals (Core Table)

```sql
CREATE TABLE hitl_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_id UUID NOT NULL REFERENCES trades(id),
    status TEXT NOT NULL CHECK (status IN (
        'AWAITING_APPROVAL',
        'APPROVED',
        'REJECTED',
        'EXPIRED'
    )),
    
    instrument TEXT NOT NULL,
    side TEXT NOT NULL,
    risk_pct DECIMAL(5,2) NOT NULL,
    confidence DECIMAL(5,2) NOT NULL,
    
    request_price DECIMAL(18,8) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    
    reasoning_summary JSONB NOT NULL,
    
    requested_at TIMESTAMP NOT NULL DEFAULT now(),
    decided_at TIMESTAMP,
    decided_by TEXT,
    decision_channel TEXT,
    decision_reason TEXT,
    
    correlation_id UUID NOT NULL,
    row_hash CHAR(64) NOT NULL,
    
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);
```

### 4. Indexes (Performance + Safety)

```sql
CREATE INDEX idx_hitl_pending ON hitl_approvals (status, expires_at);
CREATE INDEX idx_hitl_trade ON hitl_approvals (trade_id);
CREATE INDEX idx_hitl_correlation ON hitl_approvals (correlation_id);
```

### 5. post_trade_snapshots

```sql
CREATE TABLE post_trade_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    approval_id UUID REFERENCES hitl_approvals(id),
    
    bid DECIMAL(18,8),
    ask DECIMAL(18,8),
    spread DECIMAL(18,8),
    mid_price DECIMAL(18,8),
    
    price_deviation_pct DECIMAL(6,3),
    response_latency_ms INT,
    
    correlation_id UUID NOT NULL,
    created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_snapshot_approval ON post_trade_snapshots (approval_id);
CREATE INDEX idx_snapshot_correlation ON post_trade_snapshots (correlation_id);
```

### 6. audit_log (Immutable)

```sql
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id TEXT,
    actor_role TEXT,
    action TEXT NOT NULL,
    target_type TEXT,
    target_id UUID,
    result TEXT,
    metadata JSONB,
    correlation_id UUID NOT NULL,
    created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_audit_correlation ON audit_log (correlation_id);
CREATE INDEX idx_audit_target ON audit_log (target_type, target_id);
CREATE INDEX idx_audit_action ON audit_log (action, created_at);
```

### 7. user_sessions (Auth Traceability)

```sql
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    ip_address TEXT,
    device_fingerprint TEXT,
    issued_at TIMESTAMP DEFAULT now(),
    expires_at TIMESTAMP NOT NULL,
    correlation_id UUID NOT NULL
);

CREATE INDEX idx_session_user ON user_sessions (user_id);
CREATE INDEX idx_session_expires ON user_sessions (expires_at);
```

### 8. deep_link_tokens

```sql
CREATE TABLE deep_link_tokens (
    token VARCHAR(64) PRIMARY KEY,
    trade_id UUID NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    correlation_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_token_expires ON deep_link_tokens (expires_at)
    WHERE used_at IS NULL;
```

## Service ↔ Requirement Map (Hard Linked)

### 🔥 HITL-GATEWAY

| Requirement | Implementation |
|-------------|----------------|
| Create approval | `INSERT hitl_approvals` |
| Timeout reject | background job |
| Slippage guard | `market-data-service` |
| Restart recovery | DB scan on boot |
| Guardian override | `guardian-service` |
| Metrics | Prometheus counters |

**Functions:**
```python
def create_approval_request(trade: Trade) -> ApprovalRequest:
    """Create new HITL approval request."""
    pass

def approve_trade(trade_id: uuid.UUID, operator: str) -> ApprovalRequest:
    """Process operator approval."""
    pass

def reject_trade(trade_id: uuid.UUID, reason: str) -> ApprovalRequest:
    """Process operator rejection."""
    pass

def recover_pending_approvals() -> List[ApprovalRequest]:
    """Recover pending approvals on startup."""
    pass
```

### 🛡️ GUARDIAN-SERVICE

| Requirement | Implementation |
|-------------|----------------|
| Lock override | Reject all pending HITL |
| Unlock with reason | `audit_log` |
| Simulate lock | Dry-run flag |

### 🔄 TRADE-LIFECYCLE

| Transition | Allowed |
|------------|---------|
| PENDING → AWAITING_APPROVAL | ✅ |
| AWAITING_APPROVAL → ACCEPTED | ✅ |
| AWAITING_APPROVAL → REJECTED | ✅ |
| ACCEPTED → FILLED | ✅ |
| FILLED → CLOSED | ✅ |
| CLOSED → SETTLED | ✅ |
| Anything else | ❌ |

Enforced via single authoritative state machine.

### 💬 DISCORD-BRIDGE

| Feature | Implementation |
|---------|----------------|
| Embed | Trade summary |
| Buttons | `trade_id` encoded |
| Deep link | one-time token |
| Update message | On decision / expiry |

### 🌐 WEBSOCKET-HUB

| Event | Payload |
|-------|---------|
| `hitl.created` | trade + timer |
| `hitl.decided` | decision |
| `guardian.locked` | reason |
| `trade.state_change` | lifecycle |

### 🧾 AUDIT-LOG-SERVICE

Every button → audit first → action second

```json
{
  "actor": "operator_123",
  "action": "HITL_APPROVE",
  "target": "trade_id",
  "result": "SUCCESS",
  "correlation_id": "uuid"
}
```

### ⏱ BACKGROUND-JOBS

| Job | Interval |
|-----|----------|
| HITL expiry | 30s |
| Restart recovery | startup |
| Websocket sync | startup |
| Deep link token cleanup | 1h |

## Environment Configuration

```bash
# HITL Gateway
HITL_ENABLED=true
HITL_TIMEOUT_SECONDS=300
HITL_SLIPPAGE_MAX_PERCENT=0.5
HITL_ALLOWED_OPERATORS=123,456

# Guardian
GUARDIAN_ADMIN_TOKEN=<secure_token>
GUARDIAN_AUDIT_DIR=data/guardian_audit

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/autonomous_alpha

# Discord
DISCORD_BOT_TOKEN=<token>
DISCORD_CHANNEL_ID=<channel_id>

# WebSocket
WEBSOCKET_PORT=8086
```

## Testing Strategy

### Property-Based Testing Framework

The design uses **Hypothesis** (Python) for property-based testing. Each correctness property maps to one or more property tests.

Configuration:
- Minimum 100 iterations per property test
- Explicit seed logging for reproducibility
- Shrinking enabled for minimal counterexamples

### Test Annotations

Each property test MUST include:
```python
# **Feature: hitl-approval-gateway, Property {N}: {property_text}**
# **Validates: Requirements X.Y**
```

### Unit Tests

Unit tests cover:
- State transition validation (valid and invalid)
- Guardian integration mocking
- Slippage calculation edge cases
- Hash computation determinism
- Configuration parsing

### Integration Tests

Integration tests cover:
- Full approval flow: create → approve → execute
- Full rejection flow: create → reject
- Timeout flow: create → expire → auto-reject
- Restart recovery: create → restart → recover
- Discord → Web deep link flow

### Test Coverage Requirements

- HITL Gateway core: 95% minimum
- API endpoints: 90% minimum
- Background workers: 85% minimum

### Chaos Testing

- Restart mid-approval (verify recovery)
- Database connection loss (verify fail-closed)
- Guardian lock during approval (verify rejection)
- Clock skew simulation (verify timeout handling)
