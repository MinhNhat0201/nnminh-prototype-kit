import { useState } from "react"

import { THEMING, getTheming, setTheming } from "@/lib/theming"

export default function Settings() {
  const [, refresh] = useState(0)
  const axes = Object.entries(THEMING).filter(([, t]) => t?.attr && (t.values?.length ?? 0) > 1)
  return (
    <section className="app-page">
      <h1>Settings</h1>
      <p>Theming attributes from ds.json &gt; theming, saved in this browser only.</p>
      <div className="app-panel">
        {axes.map(([key, t]) => (
          <label key={key} className="app-field">
            <span>{key}</span>
            <select
              value={getTheming(key)}
              onChange={(e) => {
                setTheming(key, e.target.value)
                refresh((n) => n + 1)
              }}
            >
              {t.values!.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>
    </section>
  )
}
