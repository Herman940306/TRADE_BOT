import { motion } from "framer-motion"
import { BookOpen, Target, TrendingUp, GraduationCap } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { StatusBadge } from "@/components/ui/badge"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { useLearningCurricula, useBayesianBeliefs, usePatternFingerprints } from "@/hooks/useApi"


const domainColors: Record<string, string> = {
  MARKET_STRUCTURE: "text-blue-400",
  TECHNICAL_PATTERNS: "text-purple-400",
  NEWS_IMPACT: "text-yellow-400",
  MACRO_REGIMES: "text-green-400",
  VOLATILITY_BEHAVIOR: "text-red-400",
  EXECUTION_QUALITY: "text-cyan-400",
}

export function Learning() {
  const { data: curricula } = useLearningCurricula()
  const { data: beliefs } = useBayesianBeliefs()
  const { data: patterns } = usePatternFingerprints()

  const graduated = curricula?.filter((c) => c.graduated).length ?? 0
  const totalDomains = curricula?.length ?? 0
  const avgConfidence = curricula?.length
    ? curricula.reduce((sum, c) => sum + c.confidence, 0) / curricula.length
    : 0

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold flex items-center gap-2">
        <BookOpen className="h-6 w-6 text-accent" />
        Memory &amp; Learning Viewer
      </h2>

      {/* Summary cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-sovereign-muted">Domains Graduated</p>
                <p className="text-2xl font-bold font-mono text-accent">
                  {graduated}/{totalDomains}
                </p>
              </div>
              <GraduationCap className="h-8 w-8 text-accent/40" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-sovereign-muted">Avg Confidence</p>
                <p className="text-2xl font-bold font-mono text-sovereign-text">
                  {avgConfidence.toFixed(1)}%
                </p>
              </div>
              <Target className="h-8 w-8 text-sovereign-muted/40" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-sovereign-muted">Patterns Tracked</p>
                <p className="text-2xl font-bold font-mono text-sovereign-text">
                  {patterns?.length ?? 0}
                </p>
              </div>
              <TrendingUp className="h-8 w-8 text-sovereign-muted/40" />
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="curricula">
        <TabsList>
          <TabsTrigger value="curricula">
            <BookOpen className="h-4 w-4 mr-1.5" />
            Curriculum
          </TabsTrigger>
          <TabsTrigger value="beliefs">
            <Target className="h-4 w-4 mr-1.5" />
            Bayesian Beliefs
          </TabsTrigger>
          <TabsTrigger value="patterns">
            <TrendingUp className="h-4 w-4 mr-1.5" />
            Patterns
          </TabsTrigger>
        </TabsList>

        {/* Curriculum domains */}
        <TabsContent value="curricula">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <div className="grid gap-3">
              {curricula?.map((c) => (
                <Card key={c.domain}>
                  <CardContent className="py-3 px-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className={`font-mono text-sm font-semibold ${domainColors[c.domain] ?? "text-sovereign-text"}`}>
                          {c.domain.replace(/_/g, " ")}
                        </span>
                        <StatusBadge label={c.graduated ? "GRADUATED" : "LEARNING"} />
                      </div>
                      <div className="flex items-center gap-6 text-xs text-sovereign-muted">
                        <span>Samples: <span className="font-mono text-sovereign-text">{c.samples}</span></span>
                        <span>Confidence: <span className="font-mono text-sovereign-text">{c.confidence.toFixed(1)}%</span></span>
                      </div>
                    </div>
                    {/* Confidence bar */}
                    <div className="mt-2 h-1.5 w-full rounded-full bg-sovereign-surface overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${c.graduated ? "bg-accent" : "bg-sovereign-muted"}`}
                        style={{ width: `${Math.min(c.confidence, 100)}%` }}
                      />
                    </div>
                  </CardContent>
                </Card>
              )) ?? (
                <p className="text-sm text-sovereign-muted">No curriculum data available.</p>
              )}
            </div>
          </motion.div>
        </TabsContent>

        {/* Bayesian Beliefs */}
        <TabsContent value="beliefs">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <Card>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-sovereign-border text-xs text-sovereign-muted">
                        <th className="px-4 py-3 text-left font-medium">Entity</th>
                        <th className="px-4 py-3 text-left font-medium">Domain</th>
                        <th className="px-4 py-3 text-right font-medium">Wins</th>
                        <th className="px-4 py-3 text-right font-medium">Total</th>
                        <th className="px-4 py-3 text-right font-medium">Confidence</th>
                        <th className="px-4 py-3 text-center font-medium">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {beliefs?.map((b) => (
                        <tr key={`${b.entity}-${b.domain}`} className="border-b border-sovereign-border/50 hover:bg-sovereign-card/50">
                          <td className="px-4 py-2.5 font-mono text-sovereign-text">{b.entity}</td>
                          <td className={`px-4 py-2.5 font-mono text-xs ${domainColors[b.domain] ?? ""}`}>
                            {b.domain.replace(/_/g, " ")}
                          </td>
                          <td className="px-4 py-2.5 text-right font-mono text-green-400">{b.wins}</td>
                          <td className="px-4 py-2.5 text-right font-mono">{b.total}</td>
                          <td className="px-4 py-2.5 text-right font-mono">{b.confidence.toFixed(1)}%</td>
                          <td className="px-4 py-2.5 text-center"><StatusBadge label={b.status} /></td>
                        </tr>
                      )) ?? (
                        <tr>
                          <td colSpan={6} className="px-4 py-6 text-center text-sovereign-muted">No beliefs recorded yet.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </TabsContent>

        {/* Pattern Fingerprints */}
        <TabsContent value="patterns">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <div className="grid gap-3 sm:grid-cols-2">
              {patterns?.map((p) => (
                <Card key={p.pattern_id}>
                  <CardContent className="py-3 px-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-semibold text-sm text-sovereign-text">{p.label}</span>
                      <StatusBadge label={p.regime} />
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-xs text-sovereign-muted">
                      <div>
                        Occurrences<br />
                        <span className="font-mono text-sovereign-text">{p.occurrences}</span>
                      </div>
                      <div>
                        Win Rate<br />
                        <span className={`font-mono ${p.win_rate >= 55 ? "text-green-400" : "text-sovereign-text"}`}>
                          {p.win_rate.toFixed(1)}%
                        </span>
                      </div>
                      <div>
                        Last Seen<br />
                        <span className="font-mono text-sovereign-text">
                          {new Date(p.last_seen).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )) ?? (
                <p className="text-sm text-sovereign-muted">No patterns detected yet.</p>
              )}
            </div>
          </motion.div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
