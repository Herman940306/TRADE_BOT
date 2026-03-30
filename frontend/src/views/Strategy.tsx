import { motion } from "framer-motion"
import { Swords, FlaskConical, Trophy, TrendingUp } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { StatusBadge } from "@/components/ui/badge"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { useStrategyVariants, useSandboxTrades, useStrategyStatus } from "@/hooks/useApi"
import { formatZAR } from "@/lib/utils"

const regimeColors: Record<string, string> = {
  RISK_ON: "text-green-400",
  RISK_OFF: "text-red-400",
  HIGH_VOL: "text-orange-400",
  LOW_VOL: "text-blue-400",
  TRENDING: "text-purple-400",
  RANGING: "text-yellow-400",
  NEWS_DRIVEN: "text-cyan-400",
  LIQUIDITY_DROUGHT: "text-rose-400",
}

export function Strategy() {
  const { data: strategy } = useStrategyStatus()
  const { data: variants } = useStrategyVariants()
  const { data: sandbox } = useSandboxTrades()

  const promoted = variants?.filter((v) => v.promoted).length ?? 0
  const totalVariants = variants?.length ?? 0
  const sandboxPnl = sandbox?.reduce((sum, s) => sum + s.pnl_zar, 0) ?? 0

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold flex items-center gap-2">
        <Swords className="h-6 w-6 text-accent" />
        Strategy Variants &amp; Sandbox
      </h2>

      {/* Summary cards */}
      <div className="grid gap-4 sm:grid-cols-4">
        <Card>
          <CardContent className="pt-4">
            <p className="text-xs text-sovereign-muted">Mode</p>
            <p className="text-lg font-bold font-mono">
              <StatusBadge label={strategy?.mode ?? "UNKNOWN"} />
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <p className="text-xs text-sovereign-muted">Variants</p>
            <p className="text-2xl font-bold font-mono text-sovereign-text">{totalVariants}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <p className="text-xs text-sovereign-muted">Promoted</p>
            <p className="text-2xl font-bold font-mono text-accent">{promoted}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <p className="text-xs text-sovereign-muted">Sandbox P&amp;L</p>
            <p className={`text-2xl font-bold font-mono ${sandboxPnl >= 0 ? "text-green-400" : "text-danger"}`}>
              {formatZAR(sandboxPnl)}
            </p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="variants">
        <TabsList>
          <TabsTrigger value="variants">
            <FlaskConical className="h-4 w-4 mr-1.5" />
            Variants
          </TabsTrigger>
          <TabsTrigger value="sandbox">
            <Trophy className="h-4 w-4 mr-1.5" />
            Sandbox Trades
          </TabsTrigger>
        </TabsList>

        {/* Strategy Variants */}
        <TabsContent value="variants">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <Card>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-sovereign-border text-xs text-sovereign-muted">
                        <th className="px-4 py-3 text-left font-medium">Strategy</th>
                        <th className="px-4 py-3 text-left font-medium">Regime</th>
                        <th className="px-4 py-3 text-right font-medium">Samples</th>
                        <th className="px-4 py-3 text-right font-medium">Win Rate</th>
                        <th className="px-4 py-3 text-right font-medium">Sandbox P&amp;L</th>
                        <th className="px-4 py-3 text-center font-medium">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {variants?.map((v) => (
                        <tr key={v.variant_id} className="border-b border-sovereign-border/50 hover:bg-sovereign-card/50">
                          <td className="px-4 py-2.5 font-mono text-sovereign-text">{v.strategy_name}</td>
                          <td className={`px-4 py-2.5 font-mono text-xs ${regimeColors[v.regime] ?? ""}`}>
                            {v.regime.replace(/_/g, " ")}
                          </td>
                          <td className="px-4 py-2.5 text-right font-mono">{v.samples}</td>
                          <td className={`px-4 py-2.5 text-right font-mono ${v.win_rate >= 55 ? "text-green-400" : v.win_rate < 45 ? "text-danger" : ""}`}>
                            {v.win_rate.toFixed(1)}%
                          </td>
                          <td className={`px-4 py-2.5 text-right font-mono ${v.sandbox_pnl_zar >= 0 ? "text-green-400" : "text-danger"}`}>
                            {formatZAR(v.sandbox_pnl_zar)}
                          </td>
                          <td className="px-4 py-2.5 text-center">
                            <StatusBadge label={v.promoted ? "PROMOTED" : "SANDBOX"} />
                          </td>
                        </tr>
                      )) ?? (
                        <tr>
                          <td colSpan={6} className="px-4 py-6 text-center text-sovereign-muted">No strategy variants configured.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>

            {/* Promotion criteria */}
            <Card className="mt-4">
              <CardHeader>
                <CardTitle className="text-sm flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-accent" />
                  Promotion Criteria
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4 text-xs text-sovereign-muted">
                  <div className="flex items-center justify-between rounded-lg bg-sovereign-surface p-3 border border-sovereign-border">
                    <span>Min Samples</span>
                    <span className="font-mono text-sovereign-text font-semibold">&ge; 30</span>
                  </div>
                  <div className="flex items-center justify-between rounded-lg bg-sovereign-surface p-3 border border-sovereign-border">
                    <span>Min Win Rate</span>
                    <span className="font-mono text-sovereign-text font-semibold">&ge; 55%</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </TabsContent>

        {/* Sandbox Trades */}
        <TabsContent value="sandbox">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <Card>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-sovereign-border text-xs text-sovereign-muted">
                        <th className="px-4 py-3 text-left font-medium">ID</th>
                        <th className="px-4 py-3 text-left font-medium">Strategy</th>
                        <th className="px-4 py-3 text-left font-medium">Instrument</th>
                        <th className="px-4 py-3 text-center font-medium">Signal</th>
                        <th className="px-4 py-3 text-left font-medium">Regime</th>
                        <th className="px-4 py-3 text-center font-medium">Outcome</th>
                        <th className="px-4 py-3 text-right font-medium">P&amp;L</th>
                        <th className="px-4 py-3 text-right font-medium">Date</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sandbox?.map((s) => (
                        <tr key={s.sandbox_id} className="border-b border-sovereign-border/50 hover:bg-sovereign-card/50">
                          <td className="px-4 py-2.5 font-mono text-xs text-sovereign-muted">{s.sandbox_id}</td>
                          <td className="px-4 py-2.5 font-mono text-sovereign-text">{s.strategy_variant}</td>
                          <td className="px-4 py-2.5 font-mono">{s.instrument}</td>
                          <td className="px-4 py-2.5 text-center">
                            <StatusBadge label={s.signal} />
                          </td>
                          <td className={`px-4 py-2.5 font-mono text-xs ${regimeColors[s.regime] ?? ""}`}>
                            {s.regime.replace(/_/g, " ")}
                          </td>
                          <td className="px-4 py-2.5 text-center">
                            <StatusBadge label={s.outcome} />
                          </td>
                          <td className={`px-4 py-2.5 text-right font-mono ${s.pnl_zar >= 0 ? "text-green-400" : "text-danger"}`}>
                            {formatZAR(s.pnl_zar)}
                          </td>
                          <td className="px-4 py-2.5 text-right font-mono text-xs text-sovereign-muted">
                            {new Date(s.created_at).toLocaleDateString()}
                          </td>
                        </tr>
                      )) ?? (
                        <tr>
                          <td colSpan={8} className="px-4 py-6 text-center text-sovereign-muted">No sandbox trades yet.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
