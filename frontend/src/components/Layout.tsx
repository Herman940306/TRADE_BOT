import { NavLink, Outlet } from 'react-router-dom';
import { cn } from '../lib/utils';

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard' },
  { to: '/trades', label: 'Trade History' },
  { to: '/learning', label: 'Learning' },
  { to: '/decisions', label: 'Decisions' },
  { to: '/preflight', label: 'Preflight' },
] as const;

export function Layout() {
  return (
    <div className="flex min-h-screen flex-col">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <h1 className="font-mono text-lg font-bold tracking-tight text-sovereign-400">
            Sovereign Command Hub
          </h1>
          <span className="text-xs text-gray-500">v1.8.0</span>
        </div>
      </header>

      {/* Navigation */}
      <nav className="border-b border-gray-800 bg-gray-900/50">
        <div className="mx-auto flex max-w-7xl gap-1 px-4">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                cn(
                  'border-b-2 px-3 py-2.5 text-sm font-medium transition-colors',
                  isActive
                    ? 'border-sovereign-500 text-sovereign-400'
                    : 'border-transparent text-gray-400 hover:text-gray-200',
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </div>
      </nav>

      {/* Main content */}
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800 py-3 text-center text-xs text-gray-600">
        Project Autonomous Alpha — Survival &gt; Capital Preservation &gt; Alpha
      </footer>
    </div>
  );
}
