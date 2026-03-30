import { motion } from "framer-motion"
import { Globe, Search, Database, Rss } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { StatusBadge } from "@/components/ui/badge"

const scrapingTargets = [
  { name: "ForexFactory", category: "Calendar", status: "ACTIVE", url: "forexfactory.com" },
  { name: "CoinTelegraph", category: "Crypto News", status: "ACTIVE", url: "cointelegraph.com" },
  { name: "CoinDesk", category: "Crypto News", status: "ACTIVE", url: "coindesk.com" },
  { name: "TradingView Ideas", category: "Analysis", status: "ACTIVE", url: "tradingview.com" },
  { name: "Investing.com", category: "Macro", status: "ACTIVE", url: "investing.com" },
  { name: "Reddit r/cryptocurrency", category: "Sentiment", status: "ACTIVE", url: "reddit.com" },
  { name: "Reddit r/forex", category: "Sentiment", status: "ACTIVE", url: "reddit.com" },
  { name: "Bloomberg", category: "Macro", status: "DEGRADED", url: "bloomberg.com" },
  { name: "Reuters", category: "Macro", status: "ACTIVE", url: "reuters.com" },
  { name: "GitHub Trading Repos", category: "Research", status: "ACTIVE", url: "github.com" },
]

const categoryColors: Record<string, string> = {
  Calendar: "text-blue-400",
  "Crypto News": "text-orange-400",
  Analysis: "text-purple-400",
  Macro: "text-green-400",
  Sentiment: "text-yellow-400",
  Research: "text-cyan-400",
}

export function Knowledge() {
  const activeCount = scrapingTargets.filter((t) => t.status === "ACTIVE").length

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold flex items-center gap-2">
        <Globe className="h-6 w-6 text-accent" />
        Knowledge Injection &amp; RAG
      </h2>

      {/* Summary cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-sovereign-muted">Active Sources</p>
                <p className="text-2xl font-bold font-mono text-accent">
                  {activeCount}/{scrapingTargets.length}
                </p>
              </div>
              <Rss className="h-8 w-8 text-accent/40" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-sovereign-muted">Vector Dimensions</p>
                <p className="text-2xl font-bold font-mono text-sovereign-text">768</p>
              </div>
              <Database className="h-8 w-8 text-sovereign-muted/40" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-sovereign-muted">Embedding Model</p>
                <p className="text-lg font-bold font-mono text-sovereign-text">pgvector</p>
              </div>
              <Search className="h-8 w-8 text-sovereign-muted/40" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Scraping targets */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2">
            <Globe className="h-4 w-4 text-accent" />
            Scraping Targets
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-sovereign-border text-xs text-sovereign-muted">
                  <th className="px-4 py-3 text-left font-medium">Source</th>
                  <th className="px-4 py-3 text-left font-medium">Category</th>
                  <th className="px-4 py-3 text-left font-medium">Domain</th>
                  <th className="px-4 py-3 text-center font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {scrapingTargets.map((t) => (
                  <tr key={t.name} className="border-b border-sovereign-border/50 hover:bg-sovereign-card/50">
                    <td className="px-4 py-2.5 font-semibold text-sovereign-text">{t.name}</td>
                    <td className={`px-4 py-2.5 font-mono text-xs ${categoryColors[t.category] ?? ""}`}>
                      {t.category}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs text-sovereign-muted">{t.url}</td>
                    <td className="px-4 py-2.5 text-center"><StatusBadge label={t.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* RAG Pipeline */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2">
            <Database className="h-4 w-4 text-accent" />
            RAG Pipeline
          </CardTitle>
        </CardHeader>
        <CardContent>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center gap-2 overflow-x-auto text-xs font-mono"
          >
            {[
              "Web Scrape",
              "NLP Extract",
              "Sentiment Tag",
              "Embed (768-dim)",
              "pgvector Store",
              "Semantic Search",
            ].map((step, i) => (
              <div key={step} className="flex items-center gap-2">
                <div className="shrink-0 rounded-lg bg-sovereign-surface px-3 py-2 border border-sovereign-border text-sovereign-text whitespace-nowrap">
                  {step}
                </div>
                {i < 5 && <span className="text-accent shrink-0">&rarr;</span>}
              </div>
            ))}
          </motion.div>
        </CardContent>
      </Card>
    </div>
  )
}
