import { http, HttpResponse } from "msw"

const mockPending = [
  {
    trade_id: "TRD-20250101-001",
    signal: "BUY",
    instrument: "BTC/ZAR",
    risk_pct: 2.5,
    confidence: 78.5,
    requested_at: new Date(Date.now() - 120_000).toISOString(),
    expires_at: new Date(Date.now() + 180_000).toISOString(),
    reasoning_summary: "Strong bullish divergence on 4H with volume confirmation. EMA crossover + RSI momentum aligned.",
    trend_alignment: "BULLISH",
    signal_confluence: 3,
    correlation_id: "corr-abc-123",
  },
  {
    trade_id: "TRD-20250101-002",
    signal: "SELL",
    instrument: "ETH/ZAR",
    risk_pct: 1.8,
    confidence: 65.2,
    requested_at: new Date(Date.now() - 60_000).toISOString(),
    expires_at: new Date(Date.now() + 240_000).toISOString(),
    reasoning_summary: "Bearish engulfing on daily. MACD histogram declining. Resistance rejection at R48,500.",
    trend_alignment: "BEARISH",
    signal_confluence: 2,
    correlation_id: "corr-def-456",
  },
]

const mockTrades = [
  { trade_id: "TRD-20241230-010", pair: "BTC/ZAR", state: "SETTLED", pnl_zar: 2450.0, approved_by: "sovereign", created_at: "2024-12-30T08:00:00Z", updated_at: "2024-12-30T14:00:00Z", correlation_id: "corr-settled-1" },
  { trade_id: "TRD-20241230-011", pair: "ETH/ZAR", state: "REJECTED", pnl_zar: 0, approved_by: null, created_at: "2024-12-30T09:00:00Z", updated_at: "2024-12-30T09:05:00Z", correlation_id: "corr-rejected-1" },
  { trade_id: "TRD-20241231-001", pair: "BTC/ZAR", state: "FILLED", pnl_zar: -180.5, approved_by: "sovereign", created_at: "2024-12-31T10:00:00Z", updated_at: "2024-12-31T12:00:00Z", correlation_id: "corr-filled-1" },
  { trade_id: "TRD-20241231-002", pair: "SOL/ZAR", state: "CLOSED", pnl_zar: 890.25, approved_by: "operator1", created_at: "2024-12-31T11:00:00Z", updated_at: "2024-12-31T16:00:00Z", correlation_id: "corr-closed-1" },
  { trade_id: "TRD-20250101-003", pair: "BTC/ZAR", state: "ACCEPTED", pnl_zar: 0, approved_by: "sovereign", created_at: "2025-01-01T07:00:00Z", updated_at: "2025-01-01T07:01:00Z", correlation_id: "corr-accepted-1" },
]

export const handlers = [
  // System status
  http.get("/", () =>
    HttpResponse.json({
      status: "ok",
      mode: "PAPER",
      guardian_locked: false,
      uptime_seconds: 86400,
    })
  ),

  http.get("/health", () =>
    HttpResponse.json({ status: "healthy", timestamp: new Date().toISOString() })
  ),

  // Budget
  http.get("/budget/status", () =>
    HttpResponse.json({
      budget_guard_active: true,
      daily_pnl_zar: 3250.75,
      net_alpha: 1.23,
      max_daily_loss_zar: 5000,
      trades_today: 4,
      max_trades_per_day: 10,
    })
  ),

  // Guardian
  http.get("/guardian/status", () =>
    HttpResponse.json({
      locked: false,
      lock_reason: null,
      locked_at: null,
      daily_pnl_zar: 3250.75,
      trades_blocked_count: 0,
    })
  ),

  http.post("/guardian/unlock", () =>
    HttpResponse.json({ status: "unlocked", message: "Guardian unlocked successfully" })
  ),

  // HITL
  http.get("/api/hitl/pending", () => HttpResponse.json(mockPending)),

  http.post("/api/hitl/:tradeId/approve", () =>
    HttpResponse.json({ status: "approved", message: "Trade approved successfully" })
  ),

  http.post("/api/hitl/:tradeId/reject", () =>
    HttpResponse.json({ status: "rejected", message: "Trade rejected successfully" })
  ),

  // Trade Lifecycle
  http.get("/trade-lifecycle/status", () =>
    HttpResponse.json({
      counts: {
        PENDING: 1,
        AWAITING_APPROVAL: 2,
        ACCEPTED: 1,
        FILLED: 1,
        CLOSED: 1,
        SETTLED: 1,
        REJECTED: 1,
      },
      total: 8,
    })
  ),

  http.get("/trade-lifecycle/trades/:state", ({ params }) => {
    const state = (params.state as string).toUpperCase()
    const filtered = mockTrades.filter((t) => t.state === state)
    return HttpResponse.json(filtered)
  }),

  // RGI
  http.get("/rgi/status", () =>
    HttpResponse.json({
      status: "active",
      model_loaded: true,
      last_prediction: new Date(Date.now() - 300_000).toISOString(),
    })
  ),

  // Strategy
  http.get("/strategy/status", () =>
    HttpResponse.json({
      mode: "PAPER",
      active_strategies: ["EMA_Crossover", "RSI_Momentum", "Volume_Breakout"],
    })
  ),

  // Learning endpoints
  http.get("/api/learning/curricula", () =>
    HttpResponse.json([
      { domain: "MARKET_STRUCTURE", confidence: 82.5, samples: 145, graduated: true, last_updated: new Date(Date.now() - 3_600_000).toISOString() },
      { domain: "TECHNICAL_PATTERNS", confidence: 91.2, samples: 230, graduated: true, last_updated: new Date(Date.now() - 7_200_000).toISOString() },
      { domain: "NEWS_IMPACT", confidence: 58.3, samples: 67, graduated: false, last_updated: new Date(Date.now() - 1_800_000).toISOString() },
      { domain: "MACRO_REGIMES", confidence: 74.8, samples: 112, graduated: false, last_updated: new Date(Date.now() - 14_400_000).toISOString() },
      { domain: "VOLATILITY_BEHAVIOR", confidence: 69.1, samples: 89, graduated: false, last_updated: new Date(Date.now() - 5_400_000).toISOString() },
      { domain: "EXECUTION_QUALITY", confidence: 93.7, samples: 310, graduated: true, last_updated: new Date(Date.now() - 600_000).toISOString() },
    ])
  ),

  http.get("/api/learning/beliefs", () =>
    HttpResponse.json([
      { entity: "BTC/ZAR", domain: "MARKET_STRUCTURE", wins: 28, total: 35, confidence: 78.4, status: "ACTIVE" },
      { entity: "ETH/ZAR", domain: "TECHNICAL_PATTERNS", wins: 41, total: 52, confidence: 77.8, status: "ACTIVE" },
      { entity: "SOL/ZAR", domain: "VOLATILITY_BEHAVIOR", wins: 12, total: 20, confidence: 58.3, status: "ACTIVE" },
      { entity: "EMA_Crossover", domain: "EXECUTION_QUALITY", wins: 88, total: 95, confidence: 92.1, status: "GRADUATED" },
      { entity: "RSI_Momentum", domain: "TECHNICAL_PATTERNS", wins: 65, total: 80, confidence: 80.6, status: "ACTIVE" },
      { entity: "Volume_Breakout", domain: "MARKET_STRUCTURE", wins: 15, total: 40, confidence: 38.5, status: "SUSPENDED" },
    ])
  ),

  http.get("/api/learning/patterns", () =>
    HttpResponse.json([
      { pattern_id: "PAT-001", label: "Bullish Divergence + Volume", regime: "TRENDING", occurrences: 24, win_rate: 72.5, last_seen: new Date(Date.now() - 86_400_000).toISOString() },
      { pattern_id: "PAT-002", label: "Mean Reversion @ Support", regime: "RANGING", occurrences: 18, win_rate: 61.1, last_seen: new Date(Date.now() - 172_800_000).toISOString() },
      { pattern_id: "PAT-003", label: "Breakout Failure Trap", regime: "HIGH_VOL", occurrences: 9, win_rate: 44.4, last_seen: new Date(Date.now() - 259_200_000).toISOString() },
      { pattern_id: "PAT-004", label: "News Catalyst Fade", regime: "NEWS_DRIVEN", occurrences: 14, win_rate: 57.1, last_seen: new Date(Date.now() - 43_200_000).toISOString() },
      { pattern_id: "PAT-005", label: "Low Vol Squeeze Entry", regime: "LOW_VOL", occurrences: 31, win_rate: 67.7, last_seen: new Date(Date.now() - 3_600_000).toISOString() },
      { pattern_id: "PAT-006", label: "Risk-Off Hedge Trigger", regime: "RISK_OFF", occurrences: 7, win_rate: 85.7, last_seen: new Date(Date.now() - 604_800_000).toISOString() },
    ])
  ),

  // Strategy variant endpoints
  http.get("/api/strategy/variants", () =>
    HttpResponse.json([
      { variant_id: "SV-001", strategy_name: "EMA_Crossover", regime: "TRENDING", samples: 52, win_rate: 63.5, promoted: true, sandbox_pnl_zar: 4250.50 },
      { variant_id: "SV-002", strategy_name: "EMA_Crossover", regime: "RANGING", samples: 28, win_rate: 42.9, promoted: false, sandbox_pnl_zar: -1120.25 },
      { variant_id: "SV-003", strategy_name: "RSI_Momentum", regime: "HIGH_VOL", samples: 35, win_rate: 57.1, promoted: true, sandbox_pnl_zar: 2890.00 },
      { variant_id: "SV-004", strategy_name: "RSI_Momentum", regime: "LOW_VOL", samples: 41, win_rate: 51.2, promoted: false, sandbox_pnl_zar: 340.75 },
      { variant_id: "SV-005", strategy_name: "Volume_Breakout", regime: "HIGH_VOL", samples: 19, win_rate: 68.4, promoted: false, sandbox_pnl_zar: 1560.00 },
      { variant_id: "SV-006", strategy_name: "Mean_Reversion", regime: "RANGING", samples: 44, win_rate: 59.1, promoted: true, sandbox_pnl_zar: 3180.25 },
    ])
  ),

  http.get("/api/strategy/sandbox", () =>
    HttpResponse.json([
      { sandbox_id: "SBX-001", strategy_variant: "EMA_Crossover", regime: "TRENDING", instrument: "BTC/ZAR", signal: "BUY", outcome: "WIN", pnl_zar: 890.50, created_at: new Date(Date.now() - 86_400_000).toISOString() },
      { sandbox_id: "SBX-002", strategy_variant: "RSI_Momentum", regime: "HIGH_VOL", instrument: "ETH/ZAR", signal: "SELL", outcome: "WIN", pnl_zar: 420.25, created_at: new Date(Date.now() - 172_800_000).toISOString() },
      { sandbox_id: "SBX-003", strategy_variant: "Volume_Breakout", regime: "HIGH_VOL", instrument: "SOL/ZAR", signal: "BUY", outcome: "LOSS", pnl_zar: -310.00, created_at: new Date(Date.now() - 259_200_000).toISOString() },
      { sandbox_id: "SBX-004", strategy_variant: "Mean_Reversion", regime: "RANGING", instrument: "BTC/ZAR", signal: "SELL", outcome: "WIN", pnl_zar: 1250.75, created_at: new Date(Date.now() - 43_200_000).toISOString() },
      { sandbox_id: "SBX-005", strategy_variant: "EMA_Crossover", regime: "TRENDING", instrument: "ETH/ZAR", signal: "BUY", outcome: "PENDING", pnl_zar: 0, created_at: new Date(Date.now() - 3_600_000).toISOString() },
    ])
  ),

  // Metrics (text format)
  http.get("/metrics", () =>
    new HttpResponse(
      `# HELP trades_total Total trades processed\n# TYPE trades_total counter\ntrades_total 42\n`,
      { headers: { "Content-Type": "text/plain" } }
    )
  ),
]
