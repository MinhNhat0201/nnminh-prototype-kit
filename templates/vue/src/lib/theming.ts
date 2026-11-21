// Theming attributes the DS reads on <html> (ds.json > theming). Never invent other attributes.
export type ThemingKey = string
export type ThemingAxis = { attr: string; values?: string[]; default?: string }

export const APP_ID = "{{APP_ID}}"
export const THEMING: Record<ThemingKey, ThemingAxis> = {{THEMING_JSON}}

const root = document.documentElement
const storeKey = (key: string) => `${APP_ID}:${key}`

export function getTheming(key: ThemingKey): string | undefined {
  const t = THEMING[key]
  return t ? root.getAttribute(t.attr) ?? t.default ?? t.values?.[0] : undefined
}

export function setTheming(key: ThemingKey, value: string, save = true) {
  const t = THEMING[key]
  if (!t?.attr) return
  root.setAttribute(t.attr, value)
  if (save) {
    try {
      localStorage.setItem(storeKey(key), value)
    } catch {
      /* storage blocked: keep the attribute for this visit only */
    }
  }
}

/** Re-apply the values saved in this browser (localStorage, per app). */
export function restoreTheming() {
  for (const [key, t] of Object.entries(THEMING)) {
    let v: string | null = null
    try {
      v = localStorage.getItem(storeKey(key))
    } catch {
      v = null
    }
    if (t?.attr && v && (!t.values || t.values.includes(v))) setTheming(key, v, false)
  }
}

/** Light <-> dark, using ds.json > theming.mode. */
export function toggleMode() {
  const m = THEMING.mode
  if (!m?.values || m.values.length < 2) return
  const light = m.default ?? m.values[0]
  const dark = m.values.includes("dark") ? "dark" : m.values.find((v) => v !== light)!
  setTheming("mode", getTheming("mode") === dark ? light : dark)
}

/** Footer text: from <meta name="{{VERSION_META}}" data-label="..."> in index.html (sync keeps it current). */
export function versionLabel(): string {
  const meta = document.querySelector<HTMLMetaElement>('meta[name="{{VERSION_META}}"]')
  return meta?.dataset.label ?? meta?.content ?? ""
}
