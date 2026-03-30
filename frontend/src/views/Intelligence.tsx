import { motion } from "framer-motion"
import { Brain, Activity, BarChart3, ThumbsUp, Cpu } from "lucide-react"
import { useRGIStatus, useStrategyStatus } from "@/hooks/useApi"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { StatusBadge } from "@/components/ui/badge"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"

export function Intelligence() {
  const { data: rgi } = useRGIStatus()
  const { data: strategy } = useStrategyStatus()

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold flex items-center gap-2">
        <Brain className="h-6 w-6 text-accent" />
        MCP Intelligence Panel
      </h2>

      <Tabs defaultValue="reasoning">
        <TabsList>
          <TabsTrigger value="reasoning">
            <Activity className="h-4 w-4 mr-1.5" />
            Reasoning
          </TabsTrigger>
          <TabsTrigger value="calibration">
            <BarChart3 className="h-4 w-4 mr-1.5" />
            Calibration
          </TabsTrigger>
          <TabsTrigger value="rlhf">
            <ThumbsUp className="h-4 w-4 mr-1.5" />
            RLHF
          </TabsTrigger>
          <TabsTrigger value="health">
            <Cpu className="h-4 w-4 mr-1.5" />
            Model Health
          </TabsTrigger>
        </TabsList>

        {/* Reasoning Analysis */}
        <TabsContent value="reasoning">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <div className="grid gap-4 sm:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">RGI Engine Status</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-sovereign-muted">Status</span>
                    <StatusBadge label={rgi?.status?.toUpperCase() ?? "UNKNOWN"} />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-sovereign-muted">Model Loaded</span>
                    <StatusBadge label={rgi?.model_loaded ? "YES" : "NO"} />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-sovereign-muted">Last Prediction</span>
                    <span className="font-mono text-xs text-sovereign-text">
                      {rgi?.last_prediction
                        ? new Date(rgi.last_prediction).toLocaleString()
                        : "—"}
                    </span>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Strategy Engine</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-sovereign-muted">Mode</span>
                    <StatusBadge label={strategy?.mode ?? "UNKNOWN"} />
                  </div>
                  <div>
                    <p className="text-xs text-sovereign-muted mb-2">Active Strategies</p>
                    <div className="flex flex-wrap gap-1.5">
                      {strategy?.active_strategies?.map((s) => (
                        <span
                          key={s}
                          className="rounded-md bg-sovereign-surface px-2 py-0.5 text-xs font-mono text-accent border border-sovereign-border"
                        >
                          {s}
                        </span>
                      )) ?? (
                        <span className="text-xs text-sovereign-muted">None loaded</span>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            <Card className="mt-4">
              <CardHeader>
                <CardTitle className="text-sm">Reasoning Analysis</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-sovereign-muted">
                  Invoke <code className="text-accent font-mono text-xs">ml_analyze_reasoning</code> on a specific trade to see emotion analysis and reasoning safety assessment.
                  This requires the MCP Intelligence backend endpoints to be available.
                </p>
              </CardContent>
            </Card>
          </motion.div>
        </TabsContent>

        {/* Calibration */}
        <TabsContent value="calibration">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Prediction Calibration</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-sovereign-muted">
                  Calibration metrics (Brier score, ROC) will be available when the
                  <code className="text-accent font-mono text-xs ml-1">ml_get_calibration_metrics</code> endpoint is wired.
                </p>
              </CardContent>
            </Card>
          </motion.div>
        </TabsContent>

        {/* RLHF */}
        <TabsContent value="rlhf">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">RLHF Feedback</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-sovereign-muted">
                  Record prediction outcomes and view acceptance rates. Wires to
                  <code className="text-accent font-mono text-xs ml-1">ml_record_prediction_outcome</code>.
                </p>
              </CardContent>
            </Card>
          </motion.div>
        </TabsContent>

        {/* Model Health */}
        <TabsContent value="health">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Model Health Dashboard</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-4">
                  <div className="rounded-lg border border-sovereign-border bg-sovereign-surface/50 p-4 text-center">
                    <p className="text-xs text-sovereign-muted">Model Status</p>
                    <StatusBadge label={rgi?.model_loaded ? "HEALTHY" : "DEGRADED"} />
                  </div>
                  <div className="rounded-lg border border-sovereign-border bg-sovereign-surface/50 p-4 text-center">
                    <p className="text-xs text-sovereign-muted">Engine</p>
                    <p className="font-mono text-sm font-bold text-accent mt-1">qwen3:8b</p>
                  </div>
                </div>
                <p className="text-xs text-sovereign-muted">
                  Full model health dashboard requires the <code className="text-accent font-mono">ml_get_ultra_dashboard</code> MCP tool.
                </p>
              </CardContent>
            </Card>
          </motion.div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
