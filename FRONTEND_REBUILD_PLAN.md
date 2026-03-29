# Frontend Rebuild Plan

**Version:** 1.0.0
**Created:** 2026-03-29
**Classification:** Sovereign Tier Engineering — INTERNAL
**Reference:** MERGE_MASTER_PLAN.md, UNIFIED_ARCHITECTURE.md

---

## 1. Background

The legacy Sovereign Command Hub (Next.js 14) was documented in the legacy README/PRD with 10 routes and 159 Vitest tests, but **no frontend source code was shipped** in deploy.tar.gz. The frontend must be rebuilt from scratch in the new project.

---

## 2. Technology Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Framework | React 18 | Rich ecosystem, financial UI libraries, team familiarity |
| Language | TypeScript 5 | Type safety for financial data, API contracts |
| Build | Vite 5 | Fast HMR, simple config, production-optimized builds |
| Styling | Tailwind CSS 3 | Utility-first, consistent design, no CSS maintenance |
| Components | shadcn/ui | Accessible, composable, professional component library |
| State (server) | TanStack React Query v5 | Auto-refetch, cache invalidation, optimistic updates |
| State (client) | Zustand | Lightweight stores for auth, WebSocket, preferences |
| Charting | Recharts | React-native charting, Decimal-compatible |
| Routing | React Router v6 | Standard SPA routing with lazy loading |
| Icons | Lucide React | Consistent icon set matching shadcn/ui |
| Formatting | date-fns, Intl.NumberFormat | Date/currency formatting without floating-point issues |

---

## 3. Architecture

### 3.1 Directory Structure

```
frontend/
├── index.html
├── package.json
├── tsconfig.json
├── tsconfig.node.json
├── vite.config.ts
├── tailwind.config.ts
├── postcss.config.js
├── components.json              # shadcn/ui config
├── Dockerfile
├── .env.example
├── src/
│   ├── main.tsx                 # Entry point
│   ├── App.tsx                  # Root with router + providers
│   ├── vite-env.d.ts
│   │
│   ├── api/                     # Backend communication
│   │   ├── client.ts            # Axios instance with auth interceptor
│   │   ├── hooks/               # React Query hooks per domain
│   │   │   ├── useHealth.ts
│   │   │   ├── useGuardian.ts
│   │   │   ├── useHitl.ts
│   │   │   ├── useTrades.ts
│   │   │   ├── useStrategies.ts
│   │   │   ├── useLearning.ts
│   │   │   ├── useForensics.ts
│   │   │   ├── useAnalytics.ts
│   │   │   ├── useExperiments.ts
│   │   │   ├── useConfig.ts
│   │   │   ├── useAudit.ts
│   │   │   └── useMarket.ts
│   │   └── types.ts             # API response types
│   │
│   ├── ws/                      # WebSocket layer
│   │   ├── client.ts            # WebSocket connection manager
│   │   ├── events.ts            # Event type definitions
│   │   └── useWebSocket.ts      # React hook for WS events
│   │
│   ├── components/
│   │   ├── ui/                  # shadcn/ui primitives
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── badge.tsx
│   │   │   ├── table.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── toast.tsx
│   │   │   ├── tabs.tsx
│   │   │   ├── dropdown-menu.tsx
│   │   │   ├── input.tsx
│   │   │   ├── label.tsx
│   │   │   ├── separator.tsx
│   │   │   ├── skeleton.tsx
│   │   │   ├── scroll-area.tsx
│   │   │   └── progress.tsx
│   │   │
│   │   ├── layout/
│   │   │   ├── AppShell.tsx     # Main layout with sidebar
│   │   │   ├── Sidebar.tsx      # Navigation sidebar
│   │   │   ├── Header.tsx       # Top bar with status indicators
│   │   │   └── ProtectedRoute.tsx # Auth wrapper
│   │   │
│   │   ├── dashboard/
│   │   │   ├── SystemStatus.tsx  # Health/uptime/mode
│   │   │   ├── GuardianBadge.tsx # Lock status indicator
│   │   │   ├── ActiveTrades.tsx  # Current trade count
│   │   │   ├── PnlSummary.tsx   # P&L display
│   │   │   └── ModeIndicator.tsx # Current execution mode
│   │   │
│   │   ├── hitl/
│   │   │   ├── ApprovalCard.tsx  # Single approval with countdown
│   │   │   ├── ApprovalList.tsx  # Pending approvals inbox
│   │   │   ├── ApprovalDetail.tsx # Full trade context
│   │   │   └── DecisionButtons.tsx # Approve/Reject with confirmation
│   │   │
│   │   ├── guardian/
│   │   │   ├── GuardianPanel.tsx  # Full status + controls
│   │   │   ├── LockHistory.tsx   # Lock/unlock event timeline
│   │   │   └── UnlockDialog.tsx  # Admin unlock flow
│   │   │
│   │   ├── trades/
│   │   │   ├── TradeTimeline.tsx  # State transition visualization
│   │   │   ├── TradeTable.tsx    # Sortable trade history
│   │   │   ├── TradeDetail.tsx   # Full trade with all snapshots
│   │   │   └── PnlChart.tsx     # Cumulative P&L over time
│   │   │
│   │   ├── strategy/
│   │   │   ├── StrategyList.tsx  # Active strategies
│   │   │   ├── StrategyDetail.tsx # Blueprint view
│   │   │   ├── RegimeView.tsx   # Current regime + strategy mapping
│   │   │   └── GoldenSetView.tsx # Golden set evaluation results
│   │   │
│   │   ├── learning/
│   │   │   ├── LearningDashboard.tsx # 3-pillar overview
│   │   │   ├── BayesianPanel.tsx # Belief state visualization
│   │   │   ├── ConfidenceBudget.tsx # Daily budget usage
│   │   │   ├── CapitalAllocation.tsx # Confidence→size mapping
│   │   │   ├── MindStatePanel.tsx # CALM/ALERT/DEFENSIVE
│   │   │   ├── CurriculumView.tsx # Learning schedule
│   │   │   └── ExperimentCard.tsx # Experiment status
│   │   │
│   │   ├── forensics/
│   │   │   ├── SnapshotViewer.tsx # Decision snapshot explorer
│   │   │   ├── TimelineReplay.tsx # Time-travel replay
│   │   │   ├── CounterfactualView.tsx # What-if comparisons
│   │   │   └── OperatorMetrics.tsx # Operator vs AI performance
│   │   │
│   │   └── charts/
│   │       ├── EquityChart.tsx   # Equity curve
│   │       ├── DrawdownChart.tsx # Drawdown visualization
│   │       ├── ConfidenceChart.tsx # Confidence over time
│   │       └── RegimeChart.tsx  # Regime transitions
│   │
│   ├── pages/                    # Route pages
│   │   ├── LoginPage.tsx
│   │   ├── DashboardPage.tsx
│   │   ├── GuardianPage.tsx
│   │   ├── HitlPage.tsx
│   │   ├── TradesPage.tsx
│   │   ├── PaperTradingPage.tsx
│   │   ├── PreflightPage.tsx
│   │   ├── StrategyPage.tsx
│   │   ├── LearningPage.tsx
│   │   ├── ForensicsPage.tsx
│   │   ├── AnalyticsPage.tsx
│   │   ├── ExperimentsPage.tsx
│   │   ├── MarketHealthPage.tsx
│   │   ├── SettingsPage.tsx
│   │   └── LogsPage.tsx
│   │
│   ├── stores/                   # Zustand stores
│   │   ├── authStore.ts         # Operator auth state
│   │   ├── wsStore.ts           # WebSocket connection state
│   │   └── preferencesStore.ts  # UI preferences (theme, layout)
│   │
│   ├── hooks/                    # Custom hooks
│   │   ├── useAuth.ts
│   │   ├── useDecimalFormat.ts  # Format Decimal strings for display
│   │   └── useCountdown.ts     # HITL approval countdown timer
│   │
│   ├── utils/
│   │   ├── format.ts           # Number/date/currency formatting
│   │   ├── decimal.ts          # Safe Decimal string handling (no parseFloat)
│   │   └── constants.ts        # API base URL, WS URL, etc.
│   │
│   └── types/
│       ├── trade.ts
│       ├── hitl.ts
│       ├── guardian.ts
│       ├── learning.ts
│       ├── strategy.ts
│       └── system.ts
│
└── public/
    └── favicon.svg
```

### 3.2 Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **No SSR** | Operator dashboard is authenticated SPA — no SEO needed |
| **Decimal as strings** | All financial values sent as strings from backend, displayed via Intl.NumberFormat — no parseFloat |
| **React Query for server state** | Auto-refetch, background updates, stale-while-revalidate pattern |
| **Zustand for client state** | Lightweight, TypeScript-first, no boilerplate |
| **WebSocket for live updates** | HITL approvals need instant notification — polling is insufficient |
| **Lazy-loaded routes** | Each page loaded on demand — fast initial load |
| **Dark theme default** | Financial trading dashboards conventionally use dark themes |

---

## 4. Views Specification

### View 1: Login / Operator Auth

| Element | Detail |
|---------|--------|
| Route | `/login` |
| Purpose | Operator authentication |
| Backend | Bearer token validation |
| Components | LoginForm, OperatorIdInput |
| Security | Token stored in memory (Zustand), not localStorage |

### View 2: System Overview Dashboard

| Element | Detail |
|---------|--------|
| Route | `/` (default) |
| Purpose | At-a-glance system health |
| Backend | `/health`, `/guardian/status`, `/budget/status`, `/api/config/current` |
| Widgets | SystemStatus, GuardianBadge, ModeIndicator, ActiveTrades, PnlSummary, RecentActivity |
| Refresh | 30s auto-refresh + WebSocket events |

### View 3: Guardian Status & Controls

| Element | Detail |
|---------|--------|
| Route | `/guardian` |
| Purpose | Guardian monitoring and unlock |
| Backend | `/guardian/status`, `/guardian/unlock` |
| Components | GuardianPanel, LockHistory, UnlockDialog |
| Features | Lock/unlock timeline, daily loss tracking, manual unlock flow |

### View 4: HITL Approval Inbox

| Element | Detail |
|---------|--------|
| Route | `/hitl` |
| Purpose | Trade approval workflow |
| Backend | `/api/hitl/pending`, `/api/hitl/{id}/approve`, `/api/hitl/{id}/reject` |
| Components | ApprovalList, ApprovalCard (with countdown timer), ApprovalDetail, DecisionButtons |
| Real-time | WebSocket: `hitl.approval_created`, `hitl.decision_made` |
| Critical | Countdown timer for each approval (auto-reject on timeout) |

### View 5: Trade History / Lifecycle Timeline

| Element | Detail |
|---------|--------|
| Route | `/trades` |
| Purpose | Complete trade history with state transitions |
| Backend | `/api/trades/history`, `/api/trades/{id}/detail` |
| Components | TradeTable, TradeTimeline, TradeDetail, PnlChart |
| Features | Sort/filter by status, date, symbol, side. Click for detail view |

### View 6: Paper Trading View

| Element | Detail |
|---------|--------|
| Route | `/paper` |
| Purpose | DemoBroker state and paper trading activity |
| Backend | `/budget/status`, `/api/trades/history?mode=paper` |
| Components | PaperBalance, PaperPositions, PaperHistory, EquityChart |

### View 7: Live Readiness / Preflight

| Element | Detail |
|---------|--------|
| Route | `/preflight` |
| Purpose | Go/no-go checklist for live trading |
| Backend | `/api/preflight/status` |
| Components | PreflightChecklist (9 checks), ModeTransitionPanel, RolloutLimits |
| Features | Green/red status for each prerequisite |

### View 8: Strategy Management

| Element | Detail |
|---------|--------|
| Route | `/strategy` |
| Purpose | Strategy registry, regime mapping, golden set evaluation |
| Backend | `/api/strategies/list`, `/api/regimes/status` |
| Components | StrategyList, StrategyDetail, RegimeView, GoldenSetView |
| Features | View active strategies per regime, golden set evaluation scores |

### View 9: Learning / ML Dashboard

| Element | Detail |
|---------|--------|
| Route | `/learning` |
| Purpose | 3-pillar learning architecture overview |
| Backend | `/api/learning/status`, `/api/learning/bayesian` |
| Components | LearningDashboard, BayesianPanel, ConfidenceBudget, CapitalAllocation, MindStatePanel, CurriculumView |
| Features | Bayesian belief state, daily confidence budget usage, CALM/ALERT/DEFENSIVE indicator |

### View 10: Decision Forensics

| Element | Detail |
|---------|--------|
| Route | `/forensics` |
| Purpose | Time-travel decision replay, counterfactual analysis |
| Backend | `/api/decisions/snapshots`, `/api/decisions/{id}/detail` |
| Components | SnapshotViewer, TimelineReplay, CounterfactualView |
| Features | Select any past decision → see full context (market state, AI verdict, confidence, regime, mind state) |

### View 11: Operator Analytics

| Element | Detail |
|---------|--------|
| Route | `/analytics` |
| Purpose | Operator performance vs AI baseline |
| Backend | `/api/analytics/operator` |
| Components | OperatorMetrics, AccuracyChart, ValueAddChart, DecisionDistribution |
| Features | Directional accuracy, value-add vs AI auto-approve scenario |

### View 12: Experiments / Sandbox / Regime

| Element | Detail |
|---------|--------|
| Route | `/experiments` |
| Purpose | Experiment lifecycle and regime sandbox monitoring |
| Backend | `/api/experiments/list`, `/api/regimes/status` |
| Components | ExperimentCard, ExperimentTimeline, RegimeChart, SandboxTradeList |

### View 13: Market / Data Feed Health

| Element | Detail |
|---------|--------|
| Route | `/market` |
| Purpose | Data feed connectivity and freshness |
| Backend | `/api/market/health` |
| Components | FeedStatusList, LatencyChart, DataFreshnessIndicator |
| Features | Per-provider health (Binance, OANDA, TwelveData, VALR) |

### View 14: Settings / Mode Matrix / Config

| Element | Detail |
|---------|--------|
| Route | `/settings` |
| Purpose | System configuration visibility (read-only) |
| Backend | `/api/config/current` |
| Components | ConfigTable (redacted values), ModeMatrixView, RolloutLimitsView |
| Security | Secrets redacted — only non-sensitive config displayed |

### View 15: Logs / Audit / Observability

| Element | Detail |
|---------|--------|
| Route | `/logs` |
| Purpose | Audit log viewer and system log tail |
| Backend | `/api/audit/log` |
| Components | AuditTable, LogViewer, FilterPanel |
| Features | Filter by action, target_type, target_id, date range |

---

## 5. Backend API Requirements

### 5.1 New Endpoints for Frontend

| Endpoint | Method | Auth | Response Shape | Source |
|----------|--------|------|----------------|--------|
| `/api/trades/history` | GET | Bearer | `{trades: Trade[], total: number}` | trade_lifecycle table |
| `/api/trades/{id}/detail` | GET | Bearer | `{trade: Trade, snapshots: Snapshot[], transitions: Transition[]}` | trade_lifecycle + decision_snapshots |
| `/api/preflight/status` | GET | Bearer | `{checks: Check[], ready: boolean, mode: string}` | Startup safety gate |
| `/api/strategies/list` | GET | Bearer | `{strategies: Strategy[], count: number}` | strategy_store |
| `/api/learning/status` | GET | Bearer | `{bayesian: BayesianState, budget: BudgetState, mind_state: string}` | Intelligence services |
| `/api/learning/bayesian` | GET | Bearer | `{beliefs: Belief[], confidence: string, patterns: Pattern[]}` | bayesian_reasoning_service |
| `/api/decisions/snapshots` | GET | Bearer | `{snapshots: Snapshot[], total: number}` | decision_snapshots table |
| `/api/decisions/{id}/detail` | GET | Bearer | `{snapshot: FullSnapshot}` | decision_snapshots + context |
| `/api/analytics/operator` | GET | Bearer | `{accuracy: string, value_add: string, decisions: Decision[]}` | operator_analytics table |
| `/api/experiments/list` | GET | Bearer | `{experiments: Experiment[], active: number}` | experiment_definitions |
| `/api/regimes/status` | GET | Bearer | `{current: string, history: RegimeObs[]}` | regime_observations |
| `/api/config/current` | GET | Bearer | `{config: ConfigEntry[]}` | Env vars (redacted) |
| `/api/audit/log` | GET | Bearer | `{entries: AuditEntry[], total: number}` | audit_log table |
| `/api/market/health` | GET | Bearer | `{providers: ProviderHealth[]}` | Data ingestion factory |
| `/ws/events` | WS | Token | Event stream | All services |

### 5.2 WebSocket Event Types

```typescript
type WSEvent =
  | { type: 'hitl.approval_created'; data: ApprovalCreated }
  | { type: 'hitl.decision_made'; data: DecisionMade }
  | { type: 'guardian.status_changed'; data: GuardianStatus }
  | { type: 'guardian.locked'; data: LockEvent }
  | { type: 'trade.state_changed'; data: TradeStateChange }
  | { type: 'trade.filled'; data: TradeFilled }
  | { type: 'learning.update'; data: LearningUpdate }
  | { type: 'system.health'; data: HealthUpdate };
```

---

## 6. Decimal Safety in Frontend

All financial values from the backend are transmitted as **strings** and displayed using `Intl.NumberFormat` — never via `parseFloat()`.

```typescript
// ✅ CORRECT — Decimal-safe display
function formatZAR(value: string): string {
  return new Intl.NumberFormat('en-ZA', {
    style: 'currency',
    currency: 'ZAR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(value));
  // Note: Number() is acceptable for DISPLAY ONLY — never for arithmetic
}

// ❌ FORBIDDEN — floating-point arithmetic
const total = parseFloat(price) * parseFloat(quantity); // NEVER
```

---

## 7. Build & Deployment

### 7.1 Development

```bash
cd frontend
npm install
npm run dev          # Vite dev server on :5173 with proxy to :8080
```

### 7.2 Production

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

### 7.3 Docker Compose Integration

```yaml
frontend:
  build:
    context: ./frontend
    dockerfile: Dockerfile
  ports:
    - "3000:80"
  depends_on:
    - bot
  restart: unless-stopped
```

---

## 8. Implementation Priority

| Phase | Views | Priority | Effort |
|-------|-------|----------|--------|
| 1 | Login, Dashboard, Guardian, HITL | CRITICAL | 2-3 days |
| 2 | Trades, Paper Trading, Preflight | HIGH | 2 days |
| 3 | Strategy, Learning, Forensics | HIGH | 2-3 days |
| 4 | Analytics, Experiments, Market Health | MEDIUM | 1-2 days |
| 5 | Settings, Logs | LOW | 1 day |
| 6 | Polish, dark theme, responsive | LOW | 1 day |

---

*END OF FRONTEND_REBUILD_PLAN.md v1.0.0*
