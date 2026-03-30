import { StatusBadge } from "@/components/ui/badge"
import { useSystemStatus, useGuardianStatus, useBudgetStatus } from "@/hooks/useApi"
import { formatZAR } from "@/lib/utils"
import { Activity, Wifi, WifiOff } from "lucide-react"

export function TopBar() {
  const { data: system, isError: systemError } = useSystemStatus()
  const { data: guardian } = useGuardianStatus()
  const { data: budget } = useBudgetStatus()

  const health = systemError ? "CRITICAL" : system?.status === "ok" ? "HEALTHY" : "DEGRADED"
  const guardianLocked = guardian?.locked ?? system?.guardian_locked ?? false

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-sovereign-border bg-sovereign-bg/80 backdrop-blur-xl px-6">
      <div className="flex items-center gap-3">
        <h1 className="text-sm font-semibold text-sovereign-text tracking-wide">
          SOVEREIGN COMMAND HUB
        </h1>
        <span className="text-sovereign-muted text-xs font-mono">|</span>
        <StatusBadge label={health} />
      </div>

      <div className="flex items-center gap-4">
        {/* Guardian Status */}
        <StatusBadge
          label={guardianLocked ? "LOCKED" : "UNLOCKED"}
          pulse={guardianLocked}
        />

        {/* Equity */}
        {budget && (
          <div className="flex items-center gap-2 text-sm">
            <span className="text-sovereign-muted">Equity:</span>
            <span className="font-mono text-accent font-semibold">
              {formatZAR(budget.daily_pnl_zar ?? 0)}
            </span>
          </div>
        )}

        {/* Connection indicator */}
        <div className="flex items-center gap-1.5">
          {systemError ? (
            <WifiOff className="h-4 w-4 text-danger" />
          ) : (
            <Wifi className="h-4 w-4 text-success" />
          )}
          <Activity className="h-3.5 w-3.5 text-sovereign-muted animate-pulse" />
        </div>
      </div>
    </header>
  )
}
