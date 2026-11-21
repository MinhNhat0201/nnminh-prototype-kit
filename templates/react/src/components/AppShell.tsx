// App shell: top bar, navigation rail (medium and wider) <-> bottom tab bar (compact), footer with the version label.
// When catalog.md > components.map lists shell components (top bar, navigation rail, tab bar), use them instead.
import { NavLink, Outlet } from "react-router"

import { Button } from "@/components/ui/button"
import { NavIcon } from "@/components/NavIcon"
import { THEMING, toggleMode, versionLabel } from "@/lib/theming"
import { cn } from "@/lib/utils"

const NAV = [
  { to: "/", label: "Home", icon: "home" as const, end: true },
  { to: "/settings", label: "Settings", icon: "settings" as const, end: false },
]

export function AppShell() {
  const canToggle = (THEMING.mode?.values?.length ?? 0) > 1
  return (
    <div className="grid min-h-dvh grid-cols-1 grid-rows-[auto_1fr_auto] medium:grid-cols-[auto_minmax(0,1fr)]">
      <header className="sticky top-0 z-10 flex min-h-14 items-center gap-3 border-b bg-background px-4 medium:col-span-2">
        <span className="mr-auto truncate font-semibold">{"{{APP_NAME}}"}</span>
        {canToggle && (
          <Button variant="outline" size="icon" aria-label="Switch light or dark mode" title="Light or dark mode" onClick={toggleMode}>
            <NavIcon name="mode" />
          </Button>
        )}
      </header>

      <nav
        aria-label="Main"
        className="app-tabbar fixed inset-x-0 bottom-0 z-10 flex justify-around gap-1 border-t border-sidebar-border bg-sidebar px-2 pt-1 text-sidebar-foreground medium:static medium:row-span-2 medium:flex-col medium:justify-start medium:border-t-0 medium:border-r medium:p-2"
      >
        {NAV.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            end={n.end}
            className={({ isActive }) =>
              cn(
                "flex min-w-0 flex-1 flex-col items-center gap-1 rounded-md px-1 py-2 text-xs no-underline medium:min-w-18 medium:flex-none",
                isActive
                  ? "bg-sidebar-primary text-sidebar-primary-foreground"
                  : "hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
              )
            }
          >
            <NavIcon name={n.icon} />
            <span>{n.label}</span>
          </NavLink>
        ))}
      </nav>

      <main className="min-w-0 p-4 medium:p-6">
        <div className="mx-auto flex max-w-5xl flex-col gap-4">
          <Outlet />
        </div>
      </main>

      <footer className="flex flex-wrap justify-between gap-2 border-t px-6 pt-3 pb-20 text-xs text-muted-foreground medium:pb-3">
        <span>
          {"{{APP_NAME}}"} · prototype · <span data-mock="true">mock data</span>
        </span>
        <span className="app-version">{versionLabel()}</span>
      </footer>
    </div>
  )
}
