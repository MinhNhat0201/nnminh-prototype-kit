import { Link } from "react-router"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { items } from "@/lib/mock"

export default function Home() {
  return (
    <>
      <h1 className="m-0 text-2xl font-semibold">{"{{APP_NAME}}"}</h1>
      <p className="m-0 text-muted-foreground">Start screen of the prototype. Replace this content with DS components from the catalogue.</p>
      <Card>
        <CardHeader>
          <CardTitle>Recent items</CardTitle>
          <CardDescription>Mock data</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="m-0 flex list-none flex-col p-0">
            {items.map((it) => (
              <li key={it.id} className="border-t py-3 first:border-t-0">
                {it.title}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
      <div>
        <Button asChild>
          <Link to="/settings">Open settings</Link>
        </Button>
      </div>
    </>
  )
}
