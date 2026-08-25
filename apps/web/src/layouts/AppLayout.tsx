/**
 * CrimeLensAI — App Layout
 *
 * Main layout shell with sidebar navigation and content area.
 * All page routes render inside the <Outlet />.
 */

import { Outlet, NavLink } from "react-router-dom";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: "📊" },
  { to: "/cases/new", label: "Case Intake", icon: "📝" },
  { to: "/audit", label: "Audit Trail", icon: "🔗" },
];

export function AppLayout() {
  return (
    <div className="flex h-screen bg-surface-950 text-white">
      {/* ---- Sidebar ---- */}
      <aside className="w-64 bg-surface-900 border-r border-surface-800 flex flex-col">
        {/* Logo */}
        <div className="p-6 border-b border-surface-800">
          <h1 className="text-xl font-bold bg-gradient-to-r from-primary-400 to-primary-600 bg-clip-text text-transparent">
            CrimeLensAI
          </h1>
          <p className="text-xs text-surface-200 mt-1">Criminal Network Analysis</p>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200 ${
                  isActive
                    ? "bg-primary-600/20 text-primary-300 border border-primary-500/30"
                    : "text-surface-200 hover:bg-surface-800 hover:text-white"
                }`
              }
            >
              <span className="text-lg">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* User Section */}
        <div className="p-4 border-t border-surface-800">
          <div className="flex items-center gap-3 px-2">
            <div className="w-8 h-8 rounded-full bg-primary-600 flex items-center justify-center text-sm font-semibold">
              U
            </div>
            <div>
              <p className="text-sm font-medium">Investigator</p>
              <p className="text-xs text-surface-200">Role: Investigator</p>
            </div>
          </div>
        </div>
      </aside>

      {/* ---- Main Content ---- */}
      <main className="flex-1 overflow-auto">
        <div className="p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
