// App shell: top bar, navigation rail (medium and wider) <-> bottom tab bar (compact), footer with the version label.
// Skeleton classes app-* live in src/index.css. {{SHELL_NOTE}}
import { NavLink, Outlet } from "react-router"

import { NavIcon } from "@/components/NavIcon"
import { THEMING, toggleMode, versionLabel } from "@/lib/theming"

const NAV = [
  { to: "/", label: "Home", icon: "home" as const, end: true },
  { to: "/settings", label: "Settings", icon: "settings" as const, end: false },
]

export function AppShell() {
  const canToggle = (THEMING.mode?.values?.length ?? 0) > 1
  return (
    <div className="app">
      <header className="app-top">
        <span className="app-brand">{"{{APP_NAME}}"}</span>
        {canToggle && (
          <button className="app-icon-btn" type="button" aria-label="Switch light or dark mode" title="Light or dark mode" onClick={toggleMode}>
            <NavIcon name="mode" className="" />
          </button>
        )}
      </header>

      <nav className="app-nav" aria-label="Main">
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end}>
            <NavIcon name={n.icon} className="" />
            <span>{n.label}</span>
          </NavLink>
        ))}
      </nav>

      <main className="app-main">
        <Outlet />
      </main>

      <footer className="app-foot">
        <span>
          {"{{APP_NAME}}"} · prototype · <span data-mock="true">mock data</span>
        </span>
        <span className="app-version">{versionLabel()}</span>
      </footer>
    </div>
  )
}
