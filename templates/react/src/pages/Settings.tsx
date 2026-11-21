import { useState } from "react"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { THEMING, getTheming, setTheming } from "@/lib/theming"

export default function Settings() {
  const [, refresh] = useState(0)
  const axes = Object.entries(THEMING).filter(([, t]) => t?.attr && (t.values?.length ?? 0) > 1)
  return (
    <>
      <h1 className="m-0 text-2xl font-semibold">Settings</h1>
      <Card>
        <CardHeader>
          <CardTitle>Appearance</CardTitle>
          <CardDescription>Theming attributes from ds.json &gt; theming, saved in this browser only.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {axes.map(([key, t]) => (
            <label key={key} className="flex max-w-xs flex-col gap-1 text-sm">
              <span className="capitalize">{key}</span>
              <select
                className="rounded-md border border-input bg-background p-2 text-foreground"
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
        </CardContent>
      </Card>
    </>
  )
}
