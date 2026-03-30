import type {
  SystemStatus,
  HealthCheck,
  BudgetStatus,
  GuardianStatusResponse,
  PendingApproval,
  TradeLifecycleStatus,
  TradeRecord,
  RGIStatus,
  StrategyStatus,
  ApproveRequest,
  RejectRequest,
  GuardianUnlockRequest,
  LearningCurriculum,
  BayesianBelief,
  PatternFingerprint,
  StrategyVariant,
  SandboxTrade,
} from "@/types/api"

const BASE = ""

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const token = sessionStorage.getItem("auth_token")
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string>),
  }
  if (token) {
    headers["Authorization"] = `Bearer ${token}`
  }
  const res = await fetch(`${BASE}${url}`, { ...init, headers })
  if (!res.ok) {
    const body = await res.text().catch(() => "")
    throw new Error(`${res.status}: ${body || res.statusText}`)
  }
  return res.json()
}

// System
export const getSystemStatus = () => fetchJSON<SystemStatus>("/")
export const getHealth = () => fetchJSON<HealthCheck>("/health")

// Budget
export const getBudgetStatus = () => fetchJSON<BudgetStatus>("/budget/status")
export const refreshBudget = () => fetchJSON<unknown>("/budget/refresh", { method: "POST" })

// Guardian
export const getGuardianStatus = () => fetchJSON<GuardianStatusResponse>("/guardian/status")
export const unlockGuardian = (req: GuardianUnlockRequest) =>
  fetchJSON<unknown>("/guardian/unlock", {
    method: "POST",
    body: JSON.stringify(req),
  })

// HITL
export const getPendingApprovals = () => fetchJSON<PendingApproval[]>("/api/hitl/pending")
export const approveTrade = (tradeId: string, req: ApproveRequest) =>
  fetchJSON<unknown>(`/api/hitl/${encodeURIComponent(tradeId)}/approve`, {
    method: "POST",
    body: JSON.stringify(req),
  })
export const rejectTrade = (tradeId: string, req: RejectRequest) =>
  fetchJSON<unknown>(`/api/hitl/${encodeURIComponent(tradeId)}/reject`, {
    method: "POST",
    body: JSON.stringify(req),
  })

// Trade Lifecycle
export const getTradeLifecycleStatus = () => fetchJSON<TradeLifecycleStatus>("/trade-lifecycle/status")
export const getTradesByState = (state: string) =>
  fetchJSON<TradeRecord[]>(`/trade-lifecycle/trades/${encodeURIComponent(state)}`)

// RGI
export const getRGIStatus = () => fetchJSON<RGIStatus>("/rgi/status")

// Strategy
export const getStrategyStatus = () => fetchJSON<StrategyStatus>("/strategy/status")

// Learning
export const getLearningCurricula = () => fetchJSON<LearningCurriculum[]>("/api/learning/curricula")
export const getBayesianBeliefs = () => fetchJSON<BayesianBelief[]>("/api/learning/beliefs")
export const getPatternFingerprints = () => fetchJSON<PatternFingerprint[]>("/api/learning/patterns")

// Strategy Variants
export const getStrategyVariants = () => fetchJSON<StrategyVariant[]>("/api/strategy/variants")
export const getSandboxTrades = () => fetchJSON<SandboxTrade[]>("/api/strategy/sandbox")
