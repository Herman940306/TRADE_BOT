import { motion } from "framer-motion"
import { useNavigate } from "react-router-dom"
import {
  Activity,
  TrendingUp,
  AlertTriangle,
  Gavel,
  ShieldCheck,
  Brain,
  ScrollText,
  Lock,
  Flame,
} from "lucide-react"
import {
  useBudgetStatus,
  useGuardianStatus,
  useTradeLifecycleStatus,
  usePendingApprovals,
  useStrategyStatus,
  useRGIStatus,
} from "@/hooks/useApi"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { StatusBadge } from "@/components/ui/badge"
import { formatZAR, formatPercent } from "@/lib/utils"

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.08, duration: 0.4, ease: "easeOut" as const },
  }),
}

export function Dashboard() {
  const navigate = useNavigate()
  const { data: budget } = useBudgetStatus()
  const { data: guardian } = useGuardianStatus()
  const { data: lifecycle } = useTradeLifecycleStatus()
  const { data: pending } = usePendingApprovals()
  const { data: strategy } = useStrategyStatus()
  const { data: rgi } = useRGIStatus()

  const pendingCount = pending?.length ?? 0
  const tradesToday = budget?.trades_today ?? 0
  const pnlToday = budget?.daily_pnl_zar ?? 0
  const guardianLocked = guardian?.locked ?? false

  const tradeStates: Record<string, number> = lifecycle?.counts ?? {}

  return (
    <div className="space-y-6">
      {/* HITL Banner */}
      {pendingCount > 0 && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="flex items-center justify-between rounded-xl border border-accent/30 bg-accent/5 px-6 py-4 glow-accent cursor-pointer"
          onClick={() => navigate("/approvals")}
        >
          <div className="flex items-center gap-3">
            <Flame className="h-6 w-6 text-accent animate-pulse" />
            <div>
              <p className="text-lg font-bold text-accent">
                HUMAN APPROVAL QUEUE
              </p>
              <p className="text-sm text-sovereign-muted">
                {pendingCount} trade{pendingCount > 1 ? "s" : ""} awaiting your decision
              </p>
            </div>
          </div>
          <Button variant="primary" onClick={() => navigate("/approvals")}>
            Review Now
          </Button>
        </motion.div>
      )}

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          {
            label: "Trades Today",
            value: tradesToday.toString(),
            sub: `/ ${budget?.max_trades_per_day ?? "—"}`,
            icon: Activity,
            color: "text-accent",
          },
          {
            label: "P&L Today",
            value: formatZAR(pnlToday),
            sub: budget?.net_alpha ? `Alpha: ${formatPercent(budget.net_alpha)}` : undefined,
            icon: TrendingUp,
            color: pnlToday >= 0 ? "text-success" : "text-danger",
          },
          {
            label: "Risk Status",
            value: pnlToday < -(budget?.max_daily_loss_zar ?? 5000) * 0.8 ? "RED" : pnlToday < 0 ? "YELLOW" : "GREEN",
            icon: AlertTriangle,
            color: pnlToday >= 0 ? "text-success" : "text-warning",
            isBadge: true,
          },
          {
            label: "Guardian",
            value: guardianLocked ? "LOCKED" : "UNLOCKED",
            icon: ShieldCheck,
            color: guardianLocked ? "text-danger" : "text-success",
            isBadge: true,
          },
        ].map((metric, i) => (
          <motion.div
            key={metric.label}
            custom={i}
            variants={fadeUp}
            initial="hidden"
            animate="visible"
          >
            <Card className="relative overflow-hidden">
              <CardContent className="flex items-start justify-between">
                <div className="space-y-1">
                  <p className="text-xs font-medium uppercase tracking-wider text-sovereign-muted">
                    {metric.label}
                  </p>
                  {metric.isBadge ? (
                    <StatusBadge label={metric.value} pulse={metric.value === "LOCKED"} />
                  ) : (
                    <p className={`text-2xl font-bold font-mono ${metric.color}`}>
                      {metric.value}
                    </p>
                  )}
                  {metric.sub && (
                    <p className="text-xs text-sovereign-muted">{metric.sub}</p>
                  )}
                </div>
                <metric.icon className={`h-8 w-8 ${metric.color} opacity-30`} />
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Trade State Flow */}
      <motion.div custom={4} variants={fadeUp} initial="hidden" animate="visible">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ScrollText className="h-5 w-5 text-accent" />
              Trade State Flow
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap items-center justify-center gap-2">
              {(["PENDING", "AWAITING_APPROVAL", "ACCEPTED", "FILLED", "CLOSED", "SETTLED"] as const).map(
                (state, i, arr) => (
                  <div key={state} className="flex items-center gap-2">
                    <div className="flex flex-col items-center gap-1 rounded-lg border border-sovereign-border bg-sovereign-surface/50 px-4 py-3 min-w-[100px]">
                      <span className="text-xs text-sovereign-muted uppercase tracking-wider">
                        {state.replace("_", " ")}
                      </span>
                      <span className="text-xl font-bold font-mono text-accent">
                        {tradeStates[state] ?? 0}
                      </span>
                    </div>
                    {i < arr.length - 1 && (
                      <span className="text-sovereign-muted text-lg">→</span>
                    )}
                  </div>
                )
              )}
              {/* REJECTED branch */}
              <div className="flex items-center gap-2 ml-4">
                <span className="text-sovereign-muted text-sm">↗</span>
                <div className="flex flex-col items-center gap-1 rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 min-w-[100px]">
                  <span className="text-xs text-danger uppercase tracking-wider">REJECTED</span>
                  <span className="text-xl font-bold font-mono text-danger">
                    {tradeStates["REJECTED"] ?? 0}
                  </span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Quick Navigation */}
      <motion.div custom={5} variants={fadeUp} initial="hidden" animate="visible">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          {[
            { label: "Approvals", icon: Gavel, to: "/approvals", count: pendingCount },
            { label: "Trade Ledger", icon: ScrollText, to: "/trades" },
            { label: "Guardian", icon: ShieldCheck, to: "/guardian" },
            { label: "Intelligence", icon: Brain, to: "/intelligence" },
            { label: "Settings", icon: Lock, to: "/settings" },
          ].map((item) => (
            <Card
              key={item.to}
              className="cursor-pointer transition-all hover:border-accent/30 hover:glow-accent group"
              onClick={() => navigate(item.to)}
            >
              <CardContent className="flex flex-col items-center gap-2 text-center">
                <item.icon className="h-8 w-8 text-sovereign-muted group-hover:text-accent transition-colors" />
                <span className="text-sm font-medium">{item.label}</span>
                {item.count != null && item.count > 0 && (
                  <StatusBadge label={`${item.count} pending`} pulse />
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      </motion.div>

      {/* System Info Footer */}
      <motion.div custom={6} variants={fadeUp} initial="hidden" animate="visible">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Strategy Engine</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-sovereign-muted">Mode</span>
                <StatusBadge label={strategy?.mode ?? "—"} />
              </div>
              <div className="text-xs text-sovereign-muted">
                Active: {strategy?.active_strategies?.join(", ") ?? "—"}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">RGI Status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-sovereign-muted">Model</span>
                <StatusBadge label={rgi?.model_loaded ? "LOADED" : "OFFLINE"} />
              </div>
              <div className="text-xs text-sovereign-muted">
                Last prediction: {rgi?.last_prediction ? new Date(rgi.last_prediction).toLocaleTimeString() : "—"}
              </div>
            </CardContent>
          </Card>
        </div>
      </motion.div>
    </div>
  )
}
