import { NavLink } from "react-router-dom"
import {
  LayoutDashboard,
  ShieldCheck,
  Gavel,
  Brain,
  ScrollText,
  Settings,
  Shield,
  BookOpen,
  Swords,
  Globe,
  BarChart3,
} from "lucide-react"
import { cn } from "@/lib/utils"

const navItems = [
  { to: "/dashboard", icon: LayoutDashboard, label: "Pulse" },
  { to: "/approvals", icon: Gavel, label: "Approvals" },
  { to: "/trades", icon: ScrollText, label: "Ledger" },
  { to: "/guardian", icon: ShieldCheck, label: "Guardian" },
  { to: "/intelligence", icon: Brain, label: "Intel" },
  { to: "/learning", icon: BookOpen, label: "Learning" },
  { to: "/strategy", icon: Swords, label: "Strategy" },
  { to: "/knowledge", icon: Globe, label: "Knowledge" },
  { to: "/observability", icon: BarChart3, label: "Metrics" },
  { to: "/settings", icon: Settings, label: "Settings" },
] as const

interface SidebarProps {
  pendingCount?: number
}

export function Sidebar({ pendingCount = 0 }: SidebarProps) {
  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-[72px] flex-col items-center border-r border-sovereign-border bg-sovereign-surface/80 backdrop-blur-xl py-4 gap-1">
      {/* Logo */}
      <div className="mb-6 flex h-10 w-10 items-center justify-center rounded-lg bg-accent/10 border border-accent/30">
        <Shield className="h-5 w-5 text-accent" />
      </div>

      {/* Navigation */}
      <nav className="flex flex-1 flex-col items-center gap-1">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                "group relative flex h-11 w-11 items-center justify-center rounded-lg transition-all duration-200",
                isActive
                  ? "bg-accent/15 text-accent shadow-[0_0_10px_rgba(0,255,225,0.15)]"
                  : "text-sovereign-muted hover:text-sovereign-text hover:bg-sovereign-card"
              )
            }
          >
            <Icon className="h-5 w-5" />
            {/* Tooltip */}
            <span className="absolute left-full ml-3 hidden rounded-md bg-sovereign-card px-2 py-1 text-xs font-medium text-sovereign-text shadow-lg group-hover:block whitespace-nowrap border border-sovereign-border">
              {label}
            </span>
            {/* Pending badge on Approvals */}
            {to === "/approvals" && pendingCount > 0 && (
              <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-danger text-[10px] font-bold text-white px-1 animate-pulse-glow">
                {pendingCount}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Version */}
      <div className="mt-auto text-[10px] font-mono text-sovereign-muted/50">
        v1.0
      </div>
    </aside>
  )
}
