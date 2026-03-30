// Trade lifecycle states matching backend HITL state machine
export type TradeState =
  | "PENDING"
  | "AWAITING_APPROVAL"
  | "ACCEPTED"
  | "FILLED"
  | "CLOSED"
  | "SETTLED"
  | "REJECTED"

export type ApprovalStatus = "AWAITING_APPROVAL" | "ACCEPTED" | "REJECTED" | "EXPIRED"
export type GuardianStatus = "LOCKED" | "UNLOCKED"
export type SystemHealth = "HEALTHY" | "DEGRADED" | "CRITICAL"
export type RiskStatus = "GREEN" | "YELLOW" | "RED"
export type UserRole = "SOVEREIGN" | "OPERATOR" | "OBSERVER"

export interface SystemStatus {
  status: string
  mode: string
  guardian_locked: boolean
  uptime_seconds: number
}

export interface HealthCheck {
  status: string
  timestamp: string
}

export interface BudgetStatus {
  budget_guard_active: boolean
  daily_pnl_zar: number
  net_alpha: number
  max_daily_loss_zar: number
  trades_today: number
  max_trades_per_day: number
}

export interface GuardianStatusResponse {
  locked: boolean
  lock_reason: string | null
  locked_at: string | null
  daily_pnl_zar: number
  trades_blocked_count: number
}

export interface PendingApproval {
  trade_id: string
  signal: "BUY" | "SELL"
  instrument: string
  risk_pct: number
  confidence: number
  requested_at: string
  expires_at: string
  reasoning_summary: string
  trend_alignment: string
  signal_confluence: number
  correlation_id: string
}

export interface TradeRecord {
  trade_id: string
  pair: string
  state: TradeState
  pnl_zar: number
  approved_by: string | null
  created_at: string
  updated_at: string
  correlation_id: string
}

export interface TradeDetail extends TradeRecord {
  signal: "BUY" | "SELL"
  confidence: number
  risk_pct: number
  strategy_inputs: Record<string, unknown>
  strategy_outputs: Record<string, unknown>
  reasoning: string | null
  guardian_verdict: string | null
  row_hash: string
  transitions: StateTransition[]
}

export interface StateTransition {
  from_state: TradeState
  to_state: TradeState
  timestamp: string
  actor_id: string
  reason: string | null
  correlation_id: string
}

export interface TradeLifecycleStatus {
  counts: Record<TradeState, number>
  total: number
}

export interface RGIStatus {
  status: string
  model_loaded: boolean
  last_prediction: string | null
}

export interface StrategyStatus {
  mode: string
  active_strategies: string[]
}

export interface LoginRequest {
  username: string
  password: string
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: string
  role: UserRole
}

export interface UserProfile {
  user_id: string
  username: string
  role: UserRole
}

export interface GuardianUnlockRequest {
  reason: string
}

export interface ApproveRequest {
  approved_by: string
  approval_channel: string
  comment?: string
}

export interface RejectRequest {
  rejected_by: string
  rejection_channel: string
  reason?: string
}

// Learning / Memory types
export type LearningDomain =
  | "MARKET_STRUCTURE"
  | "TECHNICAL_PATTERNS"
  | "NEWS_IMPACT"
  | "MACRO_REGIMES"
  | "VOLATILITY_BEHAVIOR"
  | "EXECUTION_QUALITY"

export interface LearningCurriculum {
  domain: LearningDomain
  confidence: number
  samples: number
  graduated: boolean
  last_updated: string
}

export interface BayesianBelief {
  entity: string
  domain: LearningDomain
  wins: number
  total: number
  confidence: number
  status: "ACTIVE" | "GRADUATED" | "SUSPENDED"
}

export interface PatternFingerprint {
  pattern_id: string
  label: string
  regime: MarketRegime
  occurrences: number
  win_rate: number
  last_seen: string
}

// Strategy / Sandbox types
export type MarketRegime =
  | "RISK_ON"
  | "RISK_OFF"
  | "HIGH_VOL"
  | "LOW_VOL"
  | "TRENDING"
  | "RANGING"
  | "NEWS_DRIVEN"
  | "LIQUIDITY_DROUGHT"

export interface StrategyVariant {
  variant_id: string
  strategy_name: string
  regime: MarketRegime
  samples: number
  win_rate: number
  promoted: boolean
  sandbox_pnl_zar: number
}

export interface SandboxTrade {
  sandbox_id: string
  strategy_variant: string
  regime: MarketRegime
  instrument: string
  signal: "BUY" | "SELL"
  outcome: "WIN" | "LOSS" | "PENDING"
  pnl_zar: number
  created_at: string
}

// Observability types
export interface GrafanaDashboard {
  uid: string
  title: string
  description: string
  url: string
}
