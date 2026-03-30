import { motion } from "framer-motion"
import { BarChart3, ExternalLink, Activity, Shield, Gauge, BookOpen } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"

const GRAFANA_BASE = window.location.hostname === "localhost"
  ? "http://localhost:3000"
  : "/grafana"

const dashboards = [
  {
    uid: "sovereign_trading",
    title: "Sovereign Trading",
    description: "Core trading metrics — signals, fills, P&L, and execution latency.",
    icon: Activity,
    color: "text-accent",
  },
  {
    uid: "system-health",
    title: "System Health",
    description: "Service uptime, heartbeat, memory, CPU, and connectivity status.",
    icon: Gauge,
    color: "text-green-400",
  },
  {
    uid: "guardian",
    title: "Guardian",
    description: "Lock/unlock history, daily P&L drawdown, and blocked trade events.",
    icon: Shield,
    color: "text-red-400",
  },
  {
    uid: "trade-simulation",
    title: "Trade Simulation",
    description: "Sandbox and paper trading performance, strategy variant metrics.",
    icon: BarChart3,
    color: "text-purple-400",
  },
]

const prometheusMetrics = [
  { name: "trades_total", description: "Total trades processed" },
  { name: "trades_filled_total", description: "Trades that reached FILLED state" },
  { name: "trades_rejected_total", description: "Trades rejected by Guardian or timeout" },
  { name: "hitl_approvals_total", description: "HITL approval decisions" },
  { name: "guardian_locks_total", description: "Guardian hard-stop activations" },
  { name: "pipeline_latency_seconds", description: "End-to-end pipeline execution time" },
  { name: "webhook_requests_total", description: "TradingView webhook ingress count" },
  { name: "rgi_predictions_total", description: "RGI model inference count" },
]

export function Observability() {
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold flex items-center gap-2">
        <BarChart3 className="h-6 w-6 text-accent" />
        Observability &amp; Metrics
      </h2>

      {/* Grafana dashboards */}
      <div>
        <h3 className="text-sm font-semibold text-sovereign-muted mb-3 flex items-center gap-2">
          <BookOpen className="h-4 w-4" />
          Grafana Dashboards
        </h3>
        <div className="grid gap-4 sm:grid-cols-2">
          {dashboards.map((d) => (
            <motion.a
              key={d.uid}
              href={`${GRAFANA_BASE}/d/${d.uid}`}
              target="_blank"
              rel="noopener noreferrer"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              whileHover={{ scale: 1.02 }}
              className="block"
            >
              <Card className="h-full cursor-pointer transition-colors hover:border-accent/40">
                <CardContent className="pt-4">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`rounded-lg bg-sovereign-surface p-2 border border-sovereign-border ${d.color}`}>
                        <d.icon className="h-5 w-5" />
                      </div>
                      <div>
                        <p className="font-semibold text-sovereign-text">{d.title}</p>
                        <p className="text-xs text-sovereign-muted mt-0.5">{d.description}</p>
                      </div>
                    </div>
                    <ExternalLink className="h-4 w-4 text-sovereign-muted shrink-0 mt-1" />
                  </div>
                </CardContent>
              </Card>
            </motion.a>
          ))}
        </div>
      </div>

      {/* Prometheus metrics reference */}
      <div>
        <h3 className="text-sm font-semibold text-sovereign-muted mb-3 flex items-center gap-2">
          <Activity className="h-4 w-4" />
          Prometheus Metrics
        </h3>
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-sovereign-border text-xs text-sovereign-muted">
                    <th className="px-4 py-3 text-left font-medium">Metric</th>
                    <th className="px-4 py-3 text-left font-medium">Description</th>
                  </tr>
                </thead>
                <tbody>
                  {prometheusMetrics.map((m) => (
                    <tr key={m.name} className="border-b border-sovereign-border/50 hover:bg-sovereign-card/50">
                      <td className="px-4 py-2.5 font-mono text-xs text-accent">{m.name}</td>
                      <td className="px-4 py-2.5 text-sovereign-muted">{m.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Quick links */}
      <div className="flex gap-3 flex-wrap">
        <a
          href={`${GRAFANA_BASE}`}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 rounded-lg bg-sovereign-card px-4 py-2 text-sm font-medium text-sovereign-text border border-sovereign-border hover:border-accent/40 transition-colors"
        >
          <BarChart3 className="h-4 w-4 text-accent" />
          Open Grafana
          <ExternalLink className="h-3 w-3 text-sovereign-muted" />
        </a>
        <a
          href="/metrics"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 rounded-lg bg-sovereign-card px-4 py-2 text-sm font-medium text-sovereign-text border border-sovereign-border hover:border-accent/40 transition-colors"
        >
          <Activity className="h-4 w-4 text-purple-400" />
          Raw /metrics
          <ExternalLink className="h-3 w-3 text-sovereign-muted" />
        </a>
      </div>
    </div>
  )
}
