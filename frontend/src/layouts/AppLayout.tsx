/**
 * CrimeLensAI — App Layout
 *
 * Main layout shell with sidebar navigation and content area.
 * All page routes render inside the <Outlet />.
 */

import { useState } from "react";
import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: "📊" },
  { to: "/case-linkage", label: "Case Linkage", icon: "🔗" },
  { to: "/network", label: "Network Analysis", icon: "◉" },
  { to: "/cases/new", label: "Case Intake", icon: "📝" },
  { to: "/audit", label: "Audit Trail", icon: "📜" },
];

export function AppLayout() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="flex flex-col md:flex-row h-screen bg-surface-50 dark:bg-surface-950 text-surface-900 dark:text-white overflow-hidden transition-colors duration-200">
      {/* Mobile Top Bar */}
      <div className="md:hidden flex items-center justify-between p-4 bg-white dark:bg-surface-900 border-b border-surface-200 dark:border-surface-800 z-20 transition-colors duration-200">
        <h1 className="text-xl font-bold bg-gradient-to-r from-primary-600 to-primary-700 dark:from-primary-400 dark:to-primary-600 bg-clip-text text-transparent">
          CrimeLensAI
        </h1>
        <button 
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="text-surface-600 hover:text-surface-900 dark:text-surface-200 dark:hover:text-white p-2 transition-colors"
          aria-label="Toggle Menu"
        >
          {mobileMenuOpen ? "✕" : "☰"}
        </button>
      </div>

      {/* ---- Sidebar ---- */}
      <aside className={`
        ${mobileMenuOpen ? 'flex' : 'hidden'} 
        md:flex flex-col absolute md:relative z-10 w-full md:w-64 h-[calc(100vh-69px)] md:h-screen 
        bg-white dark:bg-surface-900 border-r border-surface-200 dark:border-surface-800 top-[69px] md:top-0 transition-colors duration-200
      `}>
        {/* Logo (Desktop only) */}
        <div className="hidden md:block p-6 border-b border-surface-200 dark:border-surface-800 transition-colors">
          <h1 className="text-xl font-bold bg-gradient-to-r from-primary-600 to-primary-700 dark:from-primary-400 dark:to-primary-600 bg-clip-text text-transparent">
            CrimeLensAI
          </h1>
          <p className="text-xs text-surface-500 dark:text-surface-200 mt-1">Criminal Network Analysis</p>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-2 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={() => setMobileMenuOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200 ${
                  isActive
                    ? "bg-primary-50 text-primary-700 shadow-sm border border-primary-100 dark:bg-primary-600/20 dark:text-primary-300 dark:border-primary-500/30 dark:shadow-none"
                    : "text-surface-600 hover:bg-surface-100 hover:text-surface-900 dark:text-surface-200 dark:hover:bg-surface-800 dark:hover:text-white border border-transparent"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* User Section & Theme Toggle */}
        <div className="p-4 border-t border-surface-200 dark:border-surface-800 transition-colors">
          <div className="flex items-center justify-between px-2 mb-3">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-8 h-8 rounded-full bg-primary-100 text-primary-700 dark:bg-primary-600 dark:text-white flex items-center justify-center text-sm font-semibold uppercase shrink-0 transition-colors">
                {user?.name?.[0] || user?.username?.[0] || "U"}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate text-surface-900 dark:text-white transition-colors">{user?.name || user?.username || "Investigator"}</p>
                <p className="text-xs text-surface-500 dark:text-surface-400 truncate transition-colors">Role: {user?.role || "Investigator"}</p>
              </div>
            </div>
            {/* Theme Toggle Button */}
            <button
              onClick={toggleTheme}
              className="p-2 rounded-lg text-surface-600 hover:bg-surface-100 dark:text-surface-300 dark:hover:bg-surface-800 transition-colors border border-transparent focus:ring-2 focus:ring-primary-500 focus:outline-none"
              title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
              aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            >
              {theme === "dark" ? "☀️" : "🌙"}
            </button>
          </div>
          <button 
            onClick={handleLogout}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 text-sm text-surface-600 hover:text-surface-900 hover:bg-surface-100 dark:text-surface-300 dark:hover:text-white dark:hover:bg-surface-800 rounded-lg transition-colors border border-transparent dark:hover:border-surface-700"
            aria-label="Logout"
          >
            <span>🚪</span> Logout
          </button>
        </div>
      </aside>

      {/* ---- Main Content ---- */}
      <main className="flex-1 overflow-y-auto relative bg-surface-50 dark:bg-surface-950 transition-colors duration-200">
        
        {/* Subtle Background Bubbles */}
        <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
          <div className="absolute -top-40 -right-40 w-96 h-96 bg-primary-300/10 dark:bg-primary-900/20 rounded-full blur-3xl opacity-50 transition-colors"></div>
          <div className="absolute top-1/4 -left-20 w-72 h-72 bg-indigo-300/10 dark:bg-indigo-900/20 rounded-full blur-3xl opacity-50 transition-colors"></div>
          <div className="absolute bottom-20 right-1/4 w-80 h-80 bg-cyan-300/10 dark:bg-cyan-900/10 rounded-full blur-3xl opacity-40 transition-colors"></div>
        </div>

        <div className="p-4 md:p-8 max-w-[1600px] mx-auto relative z-10">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
