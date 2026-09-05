import { useEffect, useRef, useState } from "react";
import { Outlet, NavLink, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { InterfaceIcon } from "../components/InterfaceIcon";
import type { InterfaceIconName } from "../components/InterfaceIcon";

const navItems: { to: string; label: string; icon: InterfaceIconName; caption: string }[] = [
  { to: "/dashboard", label: "Dashboard", icon: "dashboard", caption: "Investigation overview" },
  { to: "/cases/new", label: "Case Intake", icon: "file", caption: "Evidence intake" },
  { to: "/case-linkage", label: "Case Linkage", icon: "link", caption: "Cross-case intelligence" },
  { to: "/network", label: "Network Analysis", icon: "network", caption: "Relationship workspace" },
  { to: "/audit", label: "Audit Trail", icon: "audit", caption: "Evidence integrity" },
];

export function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const activePage = navItems.find(item => item.to === pathname);
  const name = user?.full_name || "Officer";

  useEffect(() => {
    if (!mobileMenuOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMobileMenuOpen(false);
        menuButton.current?.focus();
      }
    };
    window.addEventListener("keydown", closeOnEscape);
    const closeOnDesktop = () => { if (window.innerWidth >= 768) setMobileMenuOpen(false); };
    window.addEventListener("resize", closeOnDesktop);
    return () => {
      window.removeEventListener("keydown", closeOnEscape);
      window.removeEventListener("resize", closeOnDesktop);
    };
  }, [mobileMenuOpen]);

  return <div className="investigator-app">
    <a href="#workspace" className="skip-link">Skip to workspace</a>
    <header className="mobile-bar">
      <NavLink to="/dashboard" className="brand" onClick={() => setMobileMenuOpen(false)}>
        <span className="brand-mark"><InterfaceIcon name="shield" size={23} /></span>CrimeLens<span className="brand-ai">AI</span>
      </NavLink>
      <button ref={menuButton} type="button" className="icon-button" aria-label={mobileMenuOpen ? "Close navigation" : "Open navigation"} aria-expanded={mobileMenuOpen} aria-controls="workspace-navigation" onClick={() => setMobileMenuOpen(open => !open)}>
        <InterfaceIcon name={mobileMenuOpen ? "close" : "menu"} />
      </button>
    </header>

    <aside className={`workspace-sidebar ${mobileMenuOpen ? "is-open" : ""}`}>
      <NavLink to="/dashboard" className="desktop-brand brand" aria-label="CrimeLensAI dashboard">
        <span className="brand-mark"><InterfaceIcon name="shield" size={25} /></span>
        <span>CrimeLens<span className="brand-ai">AI</span><small>INVESTIGATION WORKSPACE</small></span>
      </NavLink>
      <nav id="workspace-navigation" aria-label="Main navigation">
        <p className="nav-section-label">WORKSPACE</p>
        {navItems.map(item => <NavLink key={item.to} to={item.to} onClick={() => setMobileMenuOpen(false)} className={({ isActive }) => `workspace-nav-link ${isActive ? "is-active" : ""}`}>
          <InterfaceIcon name={item.icon} /><span>{item.label}</span>
          <span className="nav-active-indicator" aria-hidden="true" />
        </NavLink>)}
      </nav>
      <div className="sidebar-guidance">
        <InterfaceIcon name="shield" size={18} />
        <p><strong>Evidence-led investigation</strong><span>Review every connection.<br />Protect every identity.</span></p>
      </div>
      <div className="officer-section">
        <div className="officer-profile"><span className="officer-avatar">{name[0]}</span><div><p title={name}>{name}</p><small>{(user?.role || "Investigator").replace(/_/g, " ").toLowerCase()}</small></div></div>
        <button type="button" className="sign-out" aria-label="Logout" onClick={async () => { await logout(); navigate("/login"); }}><InterfaceIcon name="logout" size={17} /> Sign out</button>
      </div>
    </aside>

    <div className="workspace-body" inert={mobileMenuOpen ? true : undefined}>
      <header className="workspace-topbar"><span>Workspace <span aria-hidden="true" className="breadcrumb-divider">/</span> <strong>{activePage?.label || "Investigation"}</strong></span><span className="workspace-context">{activePage?.caption}</span></header>
      <main id="workspace" tabIndex={-1} className="workspace-content"><Outlet /></main>
      <footer className="workspace-footer"><span>CrimeLensAI · Investigation support</span><span>Connections are leads, not conclusions.</span></footer>
    </div>
  </div>;
}
