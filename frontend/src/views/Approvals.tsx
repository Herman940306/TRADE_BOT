import { useState, useEffect, useCallback } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Check, X, Eye, Clock, TrendingUp, TrendingDown, AlertTriangle } from "lucide-react"
import { usePendingApprovals, useApproveTrade, useRejectTrade } from "@/hooks/useApi"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { StatusBadge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"

function CountdownTimer({ expiresAt }: { expiresAt: string }) {
  const [remaining, setRemaining] = useState("")
  const [urgency, setUrgency] = useState<"normal" | "warning" | "critical">("normal")

  useEffect(() => {
    const tick = () => {
      const diff = new Date(expiresAt).getTime() - Date.now()
      if (diff <= 0) {
        setRemaining("EXPIRED")
        setUrgency("critical")
        return
      }
      const mins = Math.floor(diff / 60_000)
      const secs = Math.floor((diff % 60_000) / 1000)
      setRemaining(`${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`)
      setUrgency(diff < 30_000 ? "critical" : diff < 60_000 ? "warning" : "normal")
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [expiresAt])

  const colors = {
    normal: "text-accent",
    warning: "text-warning",
    critical: "text-danger animate-pulse",
  }

  return (
    <div className="flex items-center gap-1.5">
      <Clock className={`h-4 w-4 ${colors[urgency]}`} />
      <span className={`font-mono text-lg font-bold ${colors[urgency]}`}>{remaining}</span>
    </div>
  )
}

export function Approvals() {
  const { data: pending, isLoading } = usePendingApprovals()
  const approveMutation = useApproveTrade()
  const rejectMutation = useRejectTrade()
  const [inspectTrade, setInspectTrade] = useState<string | null>(null)
  const [rejectReason, setRejectReason] = useState("")
  const [rejectDialogTradeId, setRejectDialogTradeId] = useState<string | null>(null)

  const handleApprove = useCallback(
    (tradeId: string) => {
      approveMutation.mutate({
        tradeId,
        req: { approved_by: "sovereign", approval_channel: "WEB" },
      })
    },
    [approveMutation]
  )

  const handleReject = useCallback(
    (tradeId: string) => {
      rejectMutation.mutate({
        tradeId,
        req: {
          rejected_by: "sovereign",
          rejection_channel: "WEB",
          reason: rejectReason || undefined,
        },
      })
      setRejectDialogTradeId(null)
      setRejectReason("")
    },
    [rejectMutation, rejectReason]
  )

  const inspected = pending?.find((t) => t.trade_id === inspectTrade)

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">HITL Approval Queue</h2>
        <StatusBadge
          label={`${pending?.length ?? 0} PENDING`}
          pulse={(pending?.length ?? 0) > 0}
        />
      </div>

      {!pending?.length ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <Check className="h-12 w-12 text-success mb-4 opacity-50" />
            <p className="text-lg font-medium text-sovereign-text">Queue Clear</p>
            <p className="text-sm text-sovereign-muted mt-1">No trades awaiting approval</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          <AnimatePresence mode="popLayout">
            {pending.map((trade, i) => (
              <motion.div
                key={trade.trade_id}
                layout
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0, transition: { delay: i * 0.1 } }}
                exit={{ opacity: 0, x: 20, transition: { duration: 0.2 } }}
              >
                <Card className="relative overflow-hidden border-accent/20 hover:border-accent/40 transition-colors">
                  {/* Urgency top border */}
                  <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-accent via-accent/50 to-transparent" />

                  <CardContent className="space-y-4">
                    {/* Header row */}
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div className="flex items-center gap-3">
                        <StatusBadge label={trade.signal} />
                        <div>
                          <p className="font-mono text-sm font-bold text-sovereign-text">
                            {trade.trade_id}
                          </p>
                          <p className="text-lg font-bold text-accent">{trade.instrument}</p>
                        </div>
                      </div>
                      <CountdownTimer expiresAt={trade.expires_at} />
                    </div>

                    {/* Metrics row */}
                    <div className="grid grid-cols-3 gap-4 rounded-lg bg-sovereign-surface/50 p-3">
                      <div className="text-center">
                        <p className="text-xs text-sovereign-muted uppercase tracking-wider">Risk</p>
                        <p className="font-mono text-lg font-bold text-warning">
                          {trade.risk_pct.toFixed(1)}%
                        </p>
                      </div>
                      <div className="text-center">
                        <p className="text-xs text-sovereign-muted uppercase tracking-wider">Confidence</p>
                        <p className="font-mono text-lg font-bold text-accent">
                          {trade.confidence.toFixed(1)}%
                        </p>
                      </div>
                      <div className="text-center">
                        <p className="text-xs text-sovereign-muted uppercase tracking-wider">Confluence</p>
                        <p className="font-mono text-lg font-bold text-info">
                          {trade.signal_confluence}/4
                        </p>
                      </div>
                    </div>

                    {/* Reasoning */}
                    <div className="rounded-lg border border-sovereign-border bg-sovereign-bg/50 p-3">
                      <div className="flex items-center gap-2 mb-2">
                        {trade.trend_alignment === "BULLISH" ? (
                          <TrendingUp className="h-4 w-4 text-success" />
                        ) : (
                          <TrendingDown className="h-4 w-4 text-danger" />
                        )}
                        <span className="text-xs font-medium uppercase text-sovereign-muted">
                          {trade.trend_alignment} Alignment
                        </span>
                      </div>
                      <p className="text-sm text-sovereign-text leading-relaxed">
                        {trade.reasoning_summary}
                      </p>
                    </div>

                    {/* Actions */}
                    <div className="flex flex-wrap gap-3 pt-2">
                      <Button
                        variant="success"
                        size="lg"
                        onClick={() => handleApprove(trade.trade_id)}
                        disabled={approveMutation.isPending}
                        className="flex-1 min-w-[120px]"
                      >
                        <Check className="h-5 w-5" />
                        APPROVE
                      </Button>
                      <Button
                        variant="danger"
                        size="lg"
                        onClick={() => setRejectDialogTradeId(trade.trade_id)}
                        disabled={rejectMutation.isPending}
                        className="flex-1 min-w-[120px]"
                      >
                        <X className="h-5 w-5" />
                        REJECT
                      </Button>
                      <Button
                        variant="outline"
                        size="lg"
                        onClick={() => setInspectTrade(trade.trade_id)}
                      >
                        <Eye className="h-5 w-5" />
                        INSPECT
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}

      {/* Reject Dialog */}
      <Dialog
        open={!!rejectDialogTradeId}
        onOpenChange={(open) => !open && setRejectDialogTradeId(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-danger" />
              Reject Trade
            </DialogTitle>
            <DialogDescription>
              Rejecting trade {rejectDialogTradeId}. Provide an optional reason.
            </DialogDescription>
          </DialogHeader>
          <textarea
            className="w-full rounded-lg border border-sovereign-border bg-sovereign-bg p-3 text-sm text-sovereign-text placeholder:text-sovereign-muted focus:border-accent focus:outline-none resize-none"
            rows={3}
            placeholder="Rejection reason (optional)..."
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
          />
          <div className="flex gap-3 justify-end pt-2">
            <Button variant="ghost" onClick={() => setRejectDialogTradeId(null)}>
              Cancel
            </Button>
            <Button
              variant="dangerSolid"
              onClick={() => rejectDialogTradeId && handleReject(rejectDialogTradeId)}
            >
              Confirm Reject
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Inspect Dialog */}
      <Dialog
        open={!!inspectTrade}
        onOpenChange={(open) => !open && setInspectTrade(null)}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Trade Detail — {inspected?.trade_id}</DialogTitle>
            <DialogDescription>Full forensic view of this trade</DialogDescription>
          </DialogHeader>
          {inspected && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-sovereign-muted">Instrument</p>
                  <p className="font-mono font-bold">{inspected.instrument}</p>
                </div>
                <div>
                  <p className="text-xs text-sovereign-muted">Signal</p>
                  <StatusBadge label={inspected.signal} />
                </div>
                <div>
                  <p className="text-xs text-sovereign-muted">Risk %</p>
                  <p className="font-mono">{inspected.risk_pct}%</p>
                </div>
                <div>
                  <p className="text-xs text-sovereign-muted">Confidence</p>
                  <p className="font-mono">{inspected.confidence}%</p>
                </div>
                <div>
                  <p className="text-xs text-sovereign-muted">Correlation ID</p>
                  <p className="font-mono text-xs break-all">{inspected.correlation_id}</p>
                </div>
                <div>
                  <p className="text-xs text-sovereign-muted">Requested At</p>
                  <p className="font-mono text-xs">{new Date(inspected.requested_at).toLocaleString()}</p>
                </div>
              </div>
              <div className="rounded-lg border border-sovereign-border bg-sovereign-bg/50 p-3">
                <p className="text-xs text-sovereign-muted mb-1">AI Reasoning</p>
                <p className="text-sm">{inspected.reasoning_summary}</p>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
