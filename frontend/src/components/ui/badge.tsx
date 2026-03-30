import { cn } from "@/lib/utils"
import type { SystemHealth, RiskStatus, TradeState, GuardianStatus } from "@/types/api"

type BadgeVariant = "health" | "risk" | "trade" | "guardian" | "default"

interface StatusBadgeProps {
  label: string
  variant?: BadgeVariant
  pulse?: boolean
  className?: string
}

const variantStyles: Record<string, string> = {
  HEALTHY: "bg-success/15 text-success border-success/30",
  DEGRADED: "bg-warning/15 text-warning border-warning/30",
  CRITICAL: "bg-danger/15 text-danger border-danger/30",
  GREEN: "bg-success/15 text-success border-success/30",
  YELLOW: "bg-warning/15 text-warning border-warning/30",
  RED: "bg-danger/15 text-danger border-danger/30",
  LOCKED: "bg-danger/15 text-danger border-danger/30",
  UNLOCKED: "bg-success/15 text-success border-success/30",
  PENDING: "bg-warning/15 text-warning border-warning/30",
  AWAITING_APPROVAL: "bg-accent/15 text-accent border-accent/30",
  ACCEPTED: "bg-success/15 text-success border-success/30",
  FILLED: "bg-info/15 text-info border-info/30",
  CLOSED: "bg-sovereign-muted/15 text-sovereign-muted border-sovereign-border",
  SETTLED: "bg-sovereign-muted/15 text-sovereign-muted border-sovereign-border",
  REJECTED: "bg-danger/15 text-danger border-danger/30",
  EXPIRED: "bg-danger/15 text-danger border-danger/30",
  BUY: "bg-success/15 text-success border-success/30",
  SELL: "bg-danger/15 text-danger border-danger/30",
}

export function StatusBadge({ label, pulse, className }: StatusBadgeProps) {
  const style = variantStyles[label] ?? "bg-sovereign-surface text-sovereign-muted border-sovereign-border"

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-mono font-semibold uppercase tracking-wider",
        style,
        pulse && "animate-pulse-glow",
        className
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {label}
    </span>
  )
}

export type { SystemHealth, RiskStatus, TradeState, GuardianStatus }
