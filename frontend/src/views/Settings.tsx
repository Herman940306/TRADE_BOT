import { motion } from "framer-motion"
import { Settings as SettingsIcon, Info } from "lucide-react"
import { useSystemStatus, useBudgetStatus, useGuardianStatus } from "@/hooks/useApi"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { StatusBadge } from "@/components/ui/badge"

export function Settings() {
  const { data: system } = useSystemStatus()
  const { data: budget } = useBudgetStatus()
  const { data: guardian } = useGuardianStatus()

  const configItems = [
    { label: "Execution Mode", value: system?.mode ?? "—" },
    { label: "Guardian Status", value: guardian?.locked ? "LOCKED" : "UNLOCKED" },
    { label: "Max Daily Loss (ZAR)", value: budget?.max_daily_loss_zar?.toLocaleString() ?? "—" },
    { label: "Max Trades/Day", value: budget?.max_trades_per_day?.toString() ?? "—" },
    { label: "Budget Guard Active", value: budget?.budget_guard_active ? "Yes" : "No" },
    { label: "Uptime (hours)", value: system?.uptime_seconds ? Math.floor(system.uptime_seconds / 3600).toString() : "—" },
  ]

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold flex items-center gap-2">
        <SettingsIcon className="h-6 w-6 text-accent" />
        System Configuration
      </h2>

      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2">
              <Info className="h-4 w-4 text-accent" />
              Current Configuration
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="divide-y divide-sovereign-border">
              {configItems.map((item) => (
                <div key={item.label} className="flex items-center justify-between py-3">
                  <span className="text-sm text-sovereign-muted">{item.label}</span>
                  <span className="font-mono text-sm font-semibold text-sovereign-text">
                    {item.value}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0, transition: { delay: 0.1 } }}
      >
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Frozen Configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="rounded-lg border border-warning/30 bg-warning/5 p-4">
              <p className="text-sm text-warning font-medium mb-2">
                Configuration FROZEN — Phase 12.5/13
              </p>
              <div className="space-y-1 text-xs text-sovereign-muted font-mono">
                <p>EXECUTION_THRESHOLD = 65.00</p>
                <p>REGIME_TREND_STRENGTH_MIN = 0.25</p>
                <p>REGIME_CONFIDENCE_THRESHOLD = 0.60</p>
              </div>
            </div>
            <p className="text-xs text-sovereign-muted">
              These values were locked during Phase 12.5/13 freeze approval. Modifications require a new Phase and validation cycle.
            </p>
          </CardContent>
        </Card>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0, transition: { delay: 0.2 } }}
      >
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">System Information</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-sovereign-muted">System Status</p>
                <StatusBadge label={system?.status === "ok" ? "HEALTHY" : "DEGRADED"} />
              </div>
              <div>
                <p className="text-xs text-sovereign-muted">Mode</p>
                <StatusBadge label={system?.mode ?? "UNKNOWN"} />
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  )
}
