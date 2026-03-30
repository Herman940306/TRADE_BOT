import { useState } from "react"
import { motion } from "framer-motion"
import { ScrollText, Filter } from "lucide-react"
import { useTradeLifecycleStatus, useTradesByState } from "@/hooks/useApi"
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
import { formatZAR } from "@/lib/utils"
import type { TradeState } from "@/types/api"

const ALL_STATES: TradeState[] = [
  "PENDING", "AWAITING_APPROVAL", "ACCEPTED", "FILLED", "CLOSED", "SETTLED", "REJECTED",
]

export function Trades() {
  const [selectedState, setSelectedState] = useState<string>("FILLED")
  const { data: lifecycle } = useTradeLifecycleStatus()
  const { data: trades, isLoading } = useTradesByState(selectedState)
  const [inspectId, setInspectId] = useState<string | null>(null)

  const inspected = trades?.find((t) => t.trade_id === inspectId)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold flex items-center gap-2">
          <ScrollText className="h-6 w-6 text-accent" />
          Trade Ledger
        </h2>
        <span className="text-sm text-sovereign-muted font-mono">
          {lifecycle?.total ?? 0} total trades
        </span>
      </div>

      {/* State Filter Tabs */}
      <div className="flex flex-wrap gap-2">
        <Filter className="h-5 w-5 text-sovereign-muted mt-1" />
        {ALL_STATES.map((state) => (
          <Button
            key={state}
            variant={selectedState === state ? "primary" : "ghost"}
            size="sm"
            onClick={() => setSelectedState(state)}
          >
            {state.replace("_", " ")}
            <span className="ml-1.5 text-xs opacity-70">
              ({lifecycle?.counts?.[state] ?? 0})
            </span>
          </Button>
        ))}
      </div>

      {/* Trades Table */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <Card>
          <CardContent className="p-0">
            {isLoading ? (
              <div className="flex h-32 items-center justify-center">
                <div className="h-6 w-6 animate-spin rounded-full border-2 border-accent border-t-transparent" />
              </div>
            ) : !trades?.length ? (
              <div className="flex h-32 items-center justify-center text-sovereign-muted">
                No trades in {selectedState} state
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-sovereign-border bg-sovereign-surface/50">
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-sovereign-muted">
                        Trade ID
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-sovereign-muted">
                        Pair
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-sovereign-muted">
                        State
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-sovereign-muted">
                        P&L
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-sovereign-muted">
                        Approved By
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-sovereign-muted">
                        Created
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.map((trade) => (
                      <tr
                        key={trade.trade_id}
                        className="border-b border-sovereign-border/50 hover:bg-sovereign-surface/30 cursor-pointer transition-colors"
                        onClick={() => setInspectId(trade.trade_id)}
                      >
                        <td className="px-4 py-3 font-mono text-xs text-accent">
                          {trade.trade_id}
                        </td>
                        <td className="px-4 py-3 font-mono font-semibold">
                          {trade.pair}
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge label={trade.state} />
                        </td>
                        <td
                          className={`px-4 py-3 text-right font-mono font-bold ${
                            trade.pnl_zar >= 0 ? "text-success" : "text-danger"
                          }`}
                        >
                          {formatZAR(trade.pnl_zar)}
                        </td>
                        <td className="px-4 py-3 text-sovereign-muted">
                          {trade.approved_by ?? "—"}
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-sovereign-muted">
                          {new Date(trade.created_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>

      {/* Trade Detail Dialog */}
      <Dialog open={!!inspectId} onOpenChange={(open) => !open && setInspectId(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Trade Detail — {inspected?.trade_id}</DialogTitle>
            <DialogDescription>Full lifecycle view</DialogDescription>
          </DialogHeader>
          {inspected && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-sovereign-muted">Pair</p>
                  <p className="font-mono font-bold">{inspected.pair}</p>
                </div>
                <div>
                  <p className="text-xs text-sovereign-muted">State</p>
                  <StatusBadge label={inspected.state} />
                </div>
                <div>
                  <p className="text-xs text-sovereign-muted">P&L</p>
                  <p
                    className={`font-mono font-bold ${
                      inspected.pnl_zar >= 0 ? "text-success" : "text-danger"
                    }`}
                  >
                    {formatZAR(inspected.pnl_zar)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-sovereign-muted">Approved By</p>
                  <p className="font-mono">{inspected.approved_by ?? "—"}</p>
                </div>
                <div>
                  <p className="text-xs text-sovereign-muted">Correlation ID</p>
                  <p className="font-mono text-xs break-all">{inspected.correlation_id}</p>
                </div>
                <div>
                  <p className="text-xs text-sovereign-muted">Created</p>
                  <p className="font-mono text-xs">
                    {new Date(inspected.created_at).toLocaleString()}
                  </p>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
