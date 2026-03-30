import { Outlet } from "react-router-dom"
import { Sidebar } from "./Sidebar"
import { TopBar } from "./TopBar"
import { usePendingApprovals } from "@/hooks/useApi"

export function AppShell() {
  const { data: pending } = usePendingApprovals()

  return (
    <div className="min-h-screen bg-sovereign-bg">
      <Sidebar pendingCount={pending?.length ?? 0} />
      <div className="ml-[72px] flex min-h-screen flex-col">
        <TopBar />
        <main className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
