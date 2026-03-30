import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { AppShell } from "@/components/layout/AppShell"
import { Dashboard } from "@/views/Dashboard"
import { Approvals } from "@/views/Approvals"
import { Trades } from "@/views/Trades"
import { Guardian } from "@/views/Guardian"
import { Intelligence } from "@/views/Intelligence"
import { Learning } from "@/views/Learning"
import { Strategy } from "@/views/Strategy"
import { Knowledge } from "@/views/Knowledge"
import { Observability } from "@/views/Observability"
import { Settings } from "@/views/Settings"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 5_000,
      refetchOnWindowFocus: true,
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/approvals" element={<Approvals />} />
            <Route path="/trades" element={<Trades />} />
            <Route path="/guardian" element={<Guardian />} />
            <Route path="/intelligence" element={<Intelligence />} />
            <Route path="/learning" element={<Learning />} />
            <Route path="/strategy" element={<Strategy />} />
            <Route path="/knowledge" element={<Knowledge />} />
            <Route path="/observability" element={<Observability />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
