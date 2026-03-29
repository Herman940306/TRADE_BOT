const API_BASE = '/api';

function getToken(): string {
  return localStorage.getItem('sovereign_token') ?? '';
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getToken()}`,
      ...init?.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `API error ${res.status}`);
  }

  return res.json() as Promise<T>;
}

// Trade history
export interface TradeRecord {
  correlation_id: string;
  symbol: string;
  side: string;
  order_type: string;
  quantity: string | null;
  status: string;
  created_at: string | null;
  updated_at: string | null;
}

export function fetchTradeHistory(limit = 50, offset = 0) {
  return apiFetch<{ trades: TradeRecord[]; total: number }>(
    `/trades/history?limit=${limit}&offset=${offset}`,
  );
}

// Preflight
export interface PreflightCheck {
  name: string;
  status: 'PASS' | 'FAIL';
}

export function fetchPreflight() {
  return apiFetch<{ checks: PreflightCheck[]; ready: boolean; mode: string }>(
    '/preflight/status',
  );
}

// Learning status
export interface LearningStatus {
  mind_state: string;
  curriculum_phase: number;
  curriculum_name: string;
  budget_remaining: string | null;
  budget_total: string | null;
}

export function fetchLearningStatus() {
  return apiFetch<LearningStatus>('/learning/status');
}

// Decision snapshots
export interface DecisionSnapshot {
  snapshot_id: string;
  correlation_id: string;
  confidence: string;
  mind_state: string;
  regime: string;
  strategy_name: string;
  final_size_zar: string;
  guardian_status: string;
  operator_decision: string;
  trade_id: string | null;
  outcome_pnl_zar: string | null;
  created_at: string | null;
}

export function fetchDecisionSnapshots(limit = 50) {
  return apiFetch<{ snapshots: DecisionSnapshot[]; total: number }>(
    `/decisions/snapshots?limit=${limit}`,
  );
}

// Operator analytics
export interface OperatorAnalytics {
  total_decisions: number;
  approvals: number;
  rejections: number;
  timeouts: number;
  accuracy: string | null;
  total_value_add_zar: string;
}

export function fetchOperatorAnalytics() {
  return apiFetch<OperatorAnalytics>('/analytics/operator');
}

// Regimes
export function fetchRegimeStatus() {
  return apiFetch<{
    current: { symbol: string; regime: string; confidence: string; as_of: string | null }[];
    history: { symbol: string; regime: string; confidence: string; created_at: string | null }[];
  }>('/regimes/status');
}
