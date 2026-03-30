import { useState } from "react"
import { motion } from "framer-motion"
import { Shield, ShieldOff, Unlock, History, AlertTriangle } from "lucide-react"
import { useGuardianStatus, useUnlockGuardian } from "@/hooks/useApi"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { StatusBadge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"

export function Guardian() {
  const { data: guardian, isLoading } = useGuardianStatus()
  const unlockMutation = useUnlockGuardian()
  const [unlockOpen, setUnlockOpen] = useState(false)
  const [unlockReason, setUnlockReason] = useState("")
  const [confirmChecked, setConfirmChecked] = useState(false)

  const locked = guardian?.locked ?? false

  const handleUnlock = () => {
    if (!unlockReason.trim()) return
    unlockMutation.mutate(
      { reason: unlockReason.trim() },
      {
        onSuccess: () => {
          setUnlockOpen(false)
          setUnlockReason("")
          setConfirmChecked(false)
        },
      }
    )
  }

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold flex items-center gap-2">
        <Shield className="h-6 w-6 text-accent" />
        Guardian Control Room
      </h2>

      {/* Main Status Card */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <Card
          className={`relative overflow-hidden ${
            locked ? "border-danger/40 glow-danger" : "border-success/40 glow-success"
          }`}
        >
          <div
            className={`absolute top-0 left-0 right-0 h-1 ${
              locked ? "bg-danger" : "bg-success"
            }`}
          />
          <CardContent className="flex flex-col items-center gap-6 py-10">
            {locked ? (
              <ShieldOff className="h-20 w-20 text-danger animate-pulse" />
            ) : (
              <Shield className="h-20 w-20 text-success" />
            )}

            <div className="text-center">
              <StatusBadge
                label={locked ? "LOCKED" : "UNLOCKED"}
                pulse={locked}
              />
              <p className="mt-3 text-2xl font-bold font-mono">
                System is{" "}
                <span className={locked ? "text-danger" : "text-success"}>
                  {locked ? "LOCKED" : "OPERATIONAL"}
                </span>
              </p>
            </div>

            {locked && guardian?.lock_reason && (
              <div className="w-full max-w-md rounded-lg border border-danger/30 bg-danger/5 p-4 text-center">
                <p className="text-xs text-sovereign-muted uppercase tracking-wider mb-1">
                  Lock Reason
                </p>
                <p className="text-sm text-danger">{guardian.lock_reason}</p>
                {guardian.locked_at && (
                  <p className="text-xs text-sovereign-muted mt-2">
                    Locked at: {new Date(guardian.locked_at).toLocaleString()}
                  </p>
                )}
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex gap-4 pt-4">
              {locked ? (
                <Button
                  variant="primary"
                  size="xl"
                  onClick={() => setUnlockOpen(true)}
                >
                  <Unlock className="h-5 w-5" />
                  Unlock Guardian
                </Button>
              ) : (
                <Button variant="outline" size="lg" disabled>
                  <Shield className="h-5 w-5" />
                  System Operational
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0, transition: { delay: 0.1 } }}>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Daily P&L</CardTitle>
            </CardHeader>
            <CardContent>
              <p
                className={`font-mono text-2xl font-bold ${
                  (guardian?.daily_pnl_zar ?? 0) >= 0 ? "text-success" : "text-danger"
                }`}
              >
                R {(guardian?.daily_pnl_zar ?? 0).toLocaleString("en-ZA", { minimumFractionDigits: 2 })}
              </p>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0, transition: { delay: 0.15 } }}>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Trades Blocked</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="font-mono text-2xl font-bold text-warning">
                {guardian?.trades_blocked_count ?? 0}
              </p>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0, transition: { delay: 0.2 } }}>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Lock Status</CardTitle>
            </CardHeader>
            <CardContent>
              <StatusBadge label={locked ? "LOCKED" : "UNLOCKED"} pulse={locked} />
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* Lock History Placeholder */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0, transition: { delay: 0.25 } }}>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <History className="h-4 w-4 text-accent" />
              Lock History
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-sovereign-muted">
              Lock/unlock events will appear here when the backend lock history API is available.
            </p>
          </CardContent>
        </Card>
      </motion.div>

      {/* Unlock Modal */}
      <Dialog open={unlockOpen} onOpenChange={setUnlockOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-warning" />
              Unlock Guardian
            </DialogTitle>
            <DialogDescription>
              This will re-enable trade execution. Provide a mandatory reason for the audit trail.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <textarea
              className="w-full rounded-lg border border-sovereign-border bg-sovereign-bg p-3 text-sm text-sovereign-text placeholder:text-sovereign-muted focus:border-accent focus:outline-none resize-none"
              rows={3}
              placeholder="Reason for unlocking (required)..."
              value={unlockReason}
              onChange={(e) => setUnlockReason(e.target.value)}
            />
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={confirmChecked}
                onChange={(e) => setConfirmChecked(e.target.checked)}
                className="h-4 w-4 rounded border-sovereign-border accent-accent"
              />
              <span className="text-sm text-sovereign-muted">
                I confirm I want to unlock the Guardian and resume trading
              </span>
            </label>
            <div className="flex gap-3 justify-end">
              <Button variant="ghost" onClick={() => setUnlockOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={handleUnlock}
                disabled={
                  !unlockReason.trim() || !confirmChecked || unlockMutation.isPending
                }
              >
                {unlockMutation.isPending ? "Unlocking..." : "Confirm Unlock"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
