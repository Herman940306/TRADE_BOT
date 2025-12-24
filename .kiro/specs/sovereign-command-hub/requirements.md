# Requirements Document

## Introduction

The Sovereign Command Hub is the centralized human-in-the-loop control plane for Project Autonomous Alpha. This is NOT a dashboard—it is a mission control system that provides total observability, human authority over all critical operations, mentor oversight where AI explains itself before acting, and direct system control through explicit button actions.

**Tagline:** "The bot thinks. You approve. The system never betrays you."

**Core Philosophy:**
- "Autonomy without visibility is recklessness. Visibility without control is theater."
- "Survival > Capital > Alpha"
- Read-only by default (fail-safe)
- Explicit intent required for any action
- Everything links to everything
- Every button leaves an audit trail
- Nothing bypasses Guardian

**Relationship to Existing Specs:**
- Extends `.kiro/specs/hitl-approval-gateway` with web-based approval interface
- Integrates `.kiro/specs/guardian-unlock` with web-based Guardian controls
- Integrates `.kiro/specs/trade-permission-policy` for policy visualization
- Provides unified interface for all MCP tools and observability

**Frontend Routes (React):**
- `/login` — Sovereign Access Gate
- `/dashboard` — Mission Control (Home)
- `/approvals` — HITL Approval Queue (Crown Jewel)
- `/trades` — Trade Ledger (Immutable)
- `/intelligence` — MCP Brain Viewer
- `/scraping` — Knowledge Injection Panel
- `/guardian` — Kill Switch Control
- `/settings` — System Configuration

## Glossary

- **Sovereign_Command_Hub**: The centralized web console providing human control over all Autonomous Alpha operations
- **SOVEREIGN**: Highest role with full permissions including trade approval, Guardian unlock, system configuration, and user management
- **OPERATOR**: Role with trade approval and Guardian unlock permissions, but no user management
- **OBSERVER**: Role with view-only permissions, no action buttons enabled
- **HITL_Queue**: The pending trade approval queue displayed in the web interface at `/approvals`
- **Guardian_Control_Room**: Web interface section at `/guardian` for Guardian lock/unlock operations
- **MCP_Intelligence_Panel**: Interface at `/intelligence` for interacting with ML analysis, reasoning, and calibration tools
- **Knowledge_Ingestion**: System at `/scraping` for scraping URLs and injecting content into RAG knowledge base
- **Trade_Detail_Panel**: Forensic view of a single trade showing inputs, reasoning, hash chain, and audit trail
- **Deep_Link**: Tokenized URL from Discord that opens directly to a specific trade or action in the web console
- **Post_Trade_Snapshot**: Market conditions captured at decision time for forensic analysis
- **Correlation_ID**: Unique identifier linking all operations across the system for audit traceability
- **Session_Token**: JWT-based authentication token with embedded role, user_id, and expiration
- **Refresh_Token**: Long-lived token for obtaining new Session_Tokens without re-authentication
- **Action_Confirmation_Modal**: UI pattern requiring explicit confirmation before destructive or irreversible actions
- **Decision_Channel**: Source of HITL decision (WEB, DISCORD, CLI)
- **HITL_TIMEOUT**: Automatic rejection reason when approval expires without human response
- **Row_Hash**: SHA-256 hash of record fields for tamper detection

## Requirements

### Requirement 1: Authentication and Access Control

**User Story:** As a system operator, I want secure role-based authentication with device fingerprinting, so that only authorized users can access the Command Hub and all access is logged.

#### Acceptance Criteria

1. WHEN a user visits `/login` THEN the System SHALL display username and password fields with MFA status indicator and current Guardian status
2. WHEN a user submits valid credentials THEN the System SHALL issue a JWT Session_Token containing user_id, role, and expiration timestamp plus a Refresh_Token
3. WHEN a Session_Token is issued THEN the System SHALL persist the session to the security_audit log with correlation_id, IP address, and device fingerprint
4. WHEN a user has SOVEREIGN role THEN the System SHALL enable all action buttons including trade approval, Guardian unlock, system configuration, and user management
5. WHEN a user has OPERATOR role THEN the System SHALL enable trade approval and Guardian unlock buttons but disable user management
6. WHEN a user has OBSERVER role THEN the System SHALL display all data but disable all action buttons
7. WHEN a Session_Token expires THEN the System SHALL attempt refresh via Refresh_Token before redirecting to login
8. IF authentication fails THEN the System SHALL log the attempt with IP address, device fingerprint, and increment failed_login_attempts counter

### Requirement 2: Mission Control Dashboard

**User Story:** As a system operator, I want a landing page at `/dashboard` showing system health at a glance, so that I can immediately assess if the system is alive, safe, and sane.

#### Acceptance Criteria

1. WHEN the `/dashboard` page loads THEN the System SHALL display a top bar with system status (HEALTHY/DEGRADED/CRITICAL), Guardian lock status, and current equity in ZAR format (R XXX,XXX.XX)
2. WHEN the `/dashboard` page loads THEN the System SHALL display a metrics grid showing Trades Today count, P&L Today percentage, and Risk Status (GREEN/YELLOW/RED)
3. WHEN the `/dashboard` page loads THEN the System SHALL display a live state flow visualization (Mermaid-style) showing PENDING → ACCEPTED → FILLED → CLOSED with trade counts at each node
4. WHEN trades are in AWAITING_APPROVAL state THEN the System SHALL display a prominent "HUMAN APPROVAL QUEUE" banner with pending count and fire emoji indicator
5. WHEN the `/dashboard` page loads THEN the System SHALL display navigation buttons for View Trades, Guardian, Approvals, Scraping, Intelligence, and Settings
6. WHEN active alerts exist THEN the System SHALL display alert count with severity indicators from Prometheus
7. WHEN the user clicks "Lock System NOW" THEN the System SHALL trigger Guardian emergency lock with confirmation modal and audit logging

### Requirement 3: Trade Lifecycle Visualization

**User Story:** As a system operator, I want to see all trades in a visual state machine view, so that I can track trade progression and investigate any trade's full history.

#### Acceptance Criteria

1. WHEN the Trades page loads THEN the System SHALL display a visual state machine diagram showing PENDING → AWAITING_APPROVAL → ACCEPTED → FILLED → CLOSED → SETTLED with REJECTED branch
2. WHEN trades exist in the database THEN the System SHALL display trade counts at each state node in the diagram
3. WHEN the user clicks a trade row THEN the System SHALL open the Trade_Detail_Panel as a slide-out or modal
4. WHEN the Trade_Detail_Panel opens THEN the System SHALL display strategy inputs snapshot with hash verification
5. WHEN the Trade_Detail_Panel opens THEN the System SHALL display confidence score, Guardian verdict, and policy decision
6. WHEN the Trade_Detail_Panel opens THEN the System SHALL display execution logs with timestamps and correlation_id
7. WHEN the user clicks "Explain this Trade" THEN the System SHALL invoke ml_analyze_reasoning and display the result

### Requirement 4: HITL Approval Queue Interface

**User Story:** As a system operator, I want a dedicated HITL approval interface at `/approvals` with countdown timers and one-click decisions, so that I can review and approve trades before timeout expiration.

#### Acceptance Criteria

1. WHEN trades are in AWAITING_APPROVAL state THEN the `/approvals` page SHALL display each pending trade as a card with trade_id, signal (BUY/SELL), instrument, risk percentage, and confidence score
2. WHEN a pending trade card is displayed THEN the System SHALL show a countdown timer (MM:SS format) indicating time remaining until auto-rejection
3. WHEN a pending trade card is displayed THEN the System SHALL show the reasoning summary panel with trend alignment, signal confluence, and MCP-generated explanation
4. WHEN the user clicks APPROVE THEN the System SHALL verify OPERATOR or SOVEREIGN role, validate stale price guard, and transition trade to ACCEPTED with decision_channel=WEB
5. WHEN the user clicks REJECT THEN the System SHALL prompt for optional rejection reason and transition trade to REJECTED with decision_channel=WEB
6. WHEN the user clicks INSPECT THEN the System SHALL open the Trade_Detail_Panel with full forensic view
7. WHEN no action is taken within timeout THEN the System SHALL auto-reject the trade with reason=HITL_TIMEOUT and update the UI to show "Expired - Auto Rejected"
8. WHEN an approval or rejection occurs THEN the System SHALL record decision_timestamp, decided_by, decision_channel, response_latency_ms, and correlation_id to hitl_approvals table

### Requirement 5: Guardian Control Room

**User Story:** As a system operator, I want a dedicated Guardian control interface at `/guardian`, so that I can view lock status, unlock with documented reason, and review lock history.

#### Acceptance Criteria

1. WHEN the `/guardian` page loads THEN the System SHALL display current lock status (LOCKED/UNLOCKED) with prominent visual indicator (red/green)
2. WHEN Guardian is LOCKED THEN the System SHALL display lock reason, lock timestamp (UTC), and count of trades blocked since lock
3. WHEN the user clicks "Unlock Guardian" THEN the System SHALL display a modal requiring text reason (mandatory) and confirmation checkbox
4. WHEN unlock is confirmed THEN the System SHALL invoke guardian_unlock with reason and correlation_id, persist audit record, then update UI status
5. WHEN the user clicks "Simulate Lock" THEN the System SHALL trigger Guardian lock in dry-run mode and display what would happen
6. WHEN the user clicks "View Lock History" THEN the System SHALL display chronological list of lock/unlock events with reasons, actors, and timestamps
7. IF unlock is attempted without OPERATOR or SOVEREIGN role THEN the System SHALL reject the action and log security warning with user_id

### Requirement 6: MCP Intelligence Panel

**User Story:** As a system operator, I want to interact with MCP intelligence tools at `/intelligence`, so that I can analyze reasoning, calibrate confidence, and run debates on trade decisions.

#### Acceptance Criteria

1. WHEN the `/intelligence` page loads THEN the System SHALL display tabs for Reasoning Analysis, Prediction Calibration, RLHF Feedback, and Model Health
2. WHEN the Reasoning Analysis tab is active THEN the System SHALL display current emotion analysis status and reasoning safety assessment from ml_analyze_reasoning
3. WHEN the Prediction Calibration tab is active THEN the System SHALL display calibration score, Brier score, and ROC metrics from ml_get_calibration_metrics
4. WHEN the RLHF Feedback tab is active THEN the System SHALL display acceptance rate and allow recording prediction outcomes via ml_record_prediction_outcome
5. WHEN the Model Health tab is active THEN the System SHALL display ml_get_ultra_dashboard metrics and behavioral baseline deviation
6. WHEN the user clicks "Run Debate" THEN the System SHALL invoke debate_start with the selected trade context and display debate results
7. WHEN the user clicks "Trigger Auto Adaptation" THEN the System SHALL invoke ml_trigger_auto_adaptation with documented reason and display confirmation

### Requirement 7: Knowledge Ingestion Interface

**User Story:** As a system operator, I want to inject external knowledge into the system at `/scraping`, so that I can feed market news, macro data, and sentiment sources to the AI brain.

#### Acceptance Criteria

1. WHEN the `/scraping` page loads THEN the System SHALL display a form with URL input field and buttons for Add URL, Scrape Now, and Schedule
2. WHEN the `/scraping` page loads THEN the System SHALL display a table of existing sources with URL, Status, Last Scraped timestamp, and Indexed status
3. WHEN the user clicks "Scrape Now" THEN the System SHALL scrape the URL, clean the content, and invoke rag_upsert with the processed content
4. WHEN scraping completes THEN the System SHALL display success confirmation with document_id and ingestion timestamp
5. WHEN the user clicks "Schedule" THEN the System SHALL display frequency options and invoke schedule_green_job with the specified interval
6. WHEN the user clicks "Disable" on a source THEN the System SHALL cancel the scheduled job and log the action with correlation_id
7. IF scraping fails THEN the System SHALL display error message with details and log failure with URL, error code, and stack trace
8. WHEN optional summarization is enabled THEN the System SHALL invoke Ollama for content summarization before ingestion

### Requirement 8: Observability and Forensics

**User Story:** As a system operator, I want integrated observability tools, so that I can inspect metrics, traces, logs, and alerts from a single interface.

#### Acceptance Criteria

1. WHEN the Observability page loads THEN the System SHALL display live metrics summary from get_metrics including request rates, latencies, and error counts
2. WHEN the user clicks "Inspect Trace" THEN the System SHALL invoke query_traces and display the trace timeline with span details
3. WHEN the user clicks "Open Grafana" THEN the System SHALL open the Grafana dashboard in a new tab via get_dashboard_url
4. WHEN the user clicks "View Risk History" THEN the System SHALL invoke risk_history and display chronological risk assessments
5. WHEN active alerts exist THEN the System SHALL display alert list with severity, message, and timestamp from get_alerts
6. WHEN the user selects a time range THEN the System SHALL filter all observability data to that range
7. WHEN displaying metrics THEN the System SHALL format all ZAR values with R prefix and 2-decimal precision

### Requirement 9: DAG Workflow Management

**User Story:** As a system operator, I want to visualize and execute DAG workflows, so that I can understand and control the strategy-to-execution pipeline.

#### Acceptance Criteria

1. WHEN the Workflows page loads THEN the System SHALL display existing DAG workflows with names and execution status
2. WHEN the user selects a workflow THEN the System SHALL invoke dag_visualize and display the Mermaid diagram
3. WHEN the user clicks "Execute DAG" THEN the System SHALL display confirmation modal with input parameters and invoke dag_execute
4. WHEN the user clicks "Dry Run" THEN the System SHALL invoke dag_execute with dry_run flag and display simulated results
5. WHEN a workflow execution completes THEN the System SHALL display execution results with task outcomes and timing
6. WHEN the user clicks "Create Workflow" THEN the System SHALL display workflow builder with task and dependency configuration
7. WHEN workflow execution fails THEN the System SHALL display error details and log failure with workflow_id and correlation_id

### Requirement 10: Discord Deep Linking

**User Story:** As a system operator, I want Discord notifications to link directly to the web console, so that I can take action with one click from any alert.

#### Acceptance Criteria

1. WHEN a trade enters AWAITING_APPROVAL THEN the Discord_Bridge SHALL send a message with tokenized deep link to the HITL approval page
2. WHEN a deep link is clicked THEN the System SHALL validate the token and open directly to the relevant trade or action
3. WHEN a deep link is accessed THEN the System SHALL auto-focus the APPROVE/REJECT buttons for immediate action
4. WHEN a deep link is accessed THEN the System SHALL log the access event with token_id, user_id, and timestamp for audit
5. WHEN a deep link token expires THEN the System SHALL display "Link expired" message and redirect to login
6. WHEN generating deep links THEN the System SHALL include correlation_id in the URL for traceability
7. IF a deep link is accessed by unauthorized user THEN the System SHALL reject access and log security warning

### Requirement 11: Audit Trail and Security

**User Story:** As a system architect, I want every action logged with full context, so that all operations can be reconstructed and verified for compliance.

#### Acceptance Criteria

1. WHEN any action button is clicked THEN the System SHALL log the action with user_id, role, timestamp, and correlation_id
2. WHEN a state-changing action occurs THEN the System SHALL display Action_Confirmation_Modal requiring explicit confirmation
3. WHEN an action is confirmed THEN the System SHALL persist the audit record before executing the action
4. WHEN viewing audit logs THEN the System SHALL display chronological list with action type, actor, target, and outcome
5. WHEN exporting audit data THEN the System SHALL include full context including request parameters and response status
6. WHEN a security-sensitive action fails THEN the System SHALL log the failure with error code and stack trace
7. IF CSRF token validation fails THEN the System SHALL reject the request and log security alert with request details

### Requirement 12: Real-Time Updates

**User Story:** As a system operator, I want the interface to update in real-time, so that I see current system state without manual refresh.

#### Acceptance Criteria

1. WHEN the web console is open THEN the System SHALL establish WebSocket connection for real-time updates
2. WHEN a trade state changes THEN the System SHALL push update to connected clients within 2 seconds
3. WHEN Guardian status changes THEN the System SHALL push update to connected clients immediately
4. WHEN a new alert fires THEN the System SHALL push notification to connected clients with alert details
5. WHEN WebSocket connection is lost THEN the System SHALL display connection status indicator and attempt reconnection
6. WHEN reconnection succeeds THEN the System SHALL sync current state and resume real-time updates
7. IF WebSocket is unavailable THEN the System SHALL fall back to polling with 10-second interval

### Requirement 13: Settings and Configuration

**User Story:** As a system operator, I want to view and modify system configuration, so that I can adjust operational parameters without code changes.

#### Acceptance Criteria

1. WHEN the Settings page loads THEN the System SHALL display current configuration values for HITL timeout, slippage tolerance, and trade limits
2. WHEN the user modifies a setting THEN the System SHALL validate the new value against allowed ranges
3. WHEN a setting change is confirmed THEN the System SHALL persist the change and log with correlation_id and previous value
4. WHEN displaying sensitive settings THEN the System SHALL mask values and require re-authentication to view
5. WHEN the user clicks "Export Configuration" THEN the System SHALL generate JSON export of non-sensitive settings
6. WHEN the user clicks "View Allowed Operators" THEN the System SHALL display the HITL_ALLOWED_OPERATORS whitelist
7. IF a setting change would affect safety THEN the System SHALL require OWNER role and display warning modal



### Requirement 14: HITL Database Schema

**User Story:** As a system architect, I want a dedicated HITL approvals table with immutable records, so that all approval decisions are persisted with tamper detection.

#### Acceptance Criteria

1. WHEN the database migration runs THEN the System SHALL create the hitl_approvals table with id, trade_id, status, requested_at, expires_at, decided_at, decided_by, decision_channel, decision_reason, and row_hash columns
2. WHEN a trade enters AWAITING_APPROVAL THEN the System SHALL insert a record with status='AWAITING_APPROVAL' and computed row_hash
3. WHEN a decision is made THEN the System SHALL update decided_at, decided_by, decision_channel, decision_reason, and recompute row_hash
4. WHEN status is updated THEN the System SHALL enforce CHECK constraint allowing only AWAITING_APPROVAL, APPROVED, REJECTED, or EXPIRED values
5. WHEN querying pending approvals THEN the System SHALL use the idx_hitl_pending index on (status, expires_at)
6. WHEN a record is modified THEN the System SHALL verify row_hash integrity before update to detect tampering
7. IF row_hash verification fails THEN the System SHALL reject the update and log security alert with record_id and correlation_id

### Requirement 15: Backend API Contract

**User Story:** As a frontend developer, I want a well-defined REST API contract, so that the web console can communicate with the backend reliably.

#### Acceptance Criteria

1. WHEN the frontend calls POST /api/auth/login THEN the Backend SHALL return Session_Token, Refresh_Token, and user role on success
2. WHEN the frontend calls GET /api/auth/me THEN the Backend SHALL return current user profile with role and permissions
3. WHEN the frontend calls GET /api/hitl/pending THEN the Backend SHALL return array of trades in AWAITING_APPROVAL state with countdown timers
4. WHEN the frontend calls POST /api/hitl/{trade_id}/approve THEN the Backend SHALL accept approved_by, approval_channel, and optional comment in request body
5. WHEN the frontend calls POST /api/hitl/{trade_id}/reject THEN the Backend SHALL accept rejected_by, rejection_channel, and optional reason in request body
6. WHEN the frontend calls GET /api/trades THEN the Backend SHALL return paginated trade list with filtering by state
7. WHEN the frontend calls GET /api/trades/{trade_id} THEN the Backend SHALL return full trade detail including lifecycle, strategy inputs/outputs, and MCP reasoning
8. WHEN the frontend calls POST /api/intel/reasoning THEN the Backend SHALL invoke ml_analyze_reasoning and return analysis result
9. WHEN the frontend calls POST /api/scrape THEN the Backend SHALL accept URL and targets, scrape content, and return document_id

### Requirement 16: HITL Expiry Background Job

**User Story:** As a system architect, I want a background job that auto-rejects expired approvals, so that stale trades never execute.

#### Acceptance Criteria

1. WHEN the background job runs THEN the System SHALL query all hitl_approvals with status='AWAITING_APPROVAL' and expires_at < NOW()
2. WHEN an expired approval is found THEN the System SHALL update status to 'EXPIRED' with decision_reason='HITL_TIMEOUT'
3. WHEN an approval expires THEN the System SHALL transition the associated trade to REJECTED state
4. WHEN an approval expires THEN the System SHALL send Discord notification with "Expired - Auto Rejected" message
5. WHEN the background job completes THEN the System SHALL increment hitl_expired_total Prometheus counter by count of expired approvals
6. WHEN the background job runs THEN the System SHALL execute every 30 seconds
7. IF the background job fails THEN the System SHALL log error with correlation_id and retry on next interval

### Requirement 17: Dark Mode Cyberpunk UI Theme

**User Story:** As a system operator, I want a dark mode cyberpunk-themed interface, so that the console is visually distinctive and reduces eye strain during extended monitoring.

#### Acceptance Criteria

1. WHEN the UI renders THEN the System SHALL use background color #0B0E14 (dark navy)
2. WHEN the UI renders THEN the System SHALL use accent color #00FFE1 (neon cyan) for interactive elements
3. WHEN the UI renders danger states THEN the System SHALL use color #FF4D4D (red) for alerts and rejections
4. WHEN the UI renders text THEN the System SHALL use Inter font for body text and JetBrains Mono for code and numbers
5. WHEN buttons are hovered THEN the System SHALL display subtle glow effect in accent color
6. WHEN pending approvals exist THEN the System SHALL display subtle pulse animation on the approval count badge
7. WHEN the UI renders THEN the System SHALL use rounded corners on buttons and cards for modern aesthetic

### Requirement 18: Mobile-Responsive Approval Screen

**User Story:** As a system operator, I want to approve trades from my mobile device, so that I can respond to urgent approvals when away from my desk.

#### Acceptance Criteria

1. WHEN the `/approvals` page is viewed on mobile THEN the System SHALL display a single-screen decision interface optimized for touch
2. WHEN a trade card is displayed on mobile THEN the System SHALL show instrument, side, risk percentage, and confidence in compact format
3. WHEN action buttons are displayed on mobile THEN the System SHALL render APPROVE and REJECT as large touch-friendly buttons
4. WHEN the mobile view loads THEN the System SHALL prioritize the most urgent pending approval (shortest time remaining)
5. WHEN approving on mobile THEN the System SHALL require confirmation tap to prevent accidental approvals
6. WHEN the mobile view is active THEN the System SHALL support both phone and tablet form factors
7. IF network connectivity is poor THEN the System SHALL display connection status and queue actions for retry

### Requirement 19: Trade Ledger View

**User Story:** As a system operator, I want an immutable trade ledger at `/trades`, so that I can review all historical trades with full audit trail.

#### Acceptance Criteria

1. WHEN the `/trades` page loads THEN the System SHALL display a table with Trade ID, Pair, State, P&L, and Approved By columns
2. WHEN the user clicks a trade row THEN the System SHALL open the Trade_Detail_Panel with full lifecycle view
3. WHEN the Trade_Detail_Panel opens THEN the System SHALL display state transitions with timestamps (PENDING → ACCEPTED → FILLED → CLOSED)
4. WHEN the Trade_Detail_Panel opens THEN the System SHALL display strategy inputs/outputs with hash verification
5. WHEN the Trade_Detail_Panel opens THEN the System SHALL display MCP reasoning summary and Guardian check results
6. WHEN the user applies filters THEN the System SHALL filter trades by state, date range, or instrument
7. WHEN displaying P&L THEN the System SHALL format values in ZAR with R prefix and color-code positive (green) and negative (red)
