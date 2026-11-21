import { Link } from "react-router"

import { items } from "@/lib/mock"

export default function Home() {
  return (
    <section className="app-page">
      <h1>{"{{APP_NAME}}"}</h1>
      <p>Start screen of the prototype. {"{{PAGE_NOTE}}"}</p>
      <div className="app-panel">
        <strong>Recent items</strong>
        <ul className="app-list">
          {items.map((it) => (
            <li key={it.id}>
              <Link to="/">{it.title}</Link>
            </li>
          ))}
        </ul>
      </div>
      <p>
        <Link to="/settings">Open settings</Link>
      </p>
    </section>
  )
}
