// Hash history router: the static build opens from a folder; #/ is home; unknown paths go home; Back/Forward work.
// One route per page; pages live in src/pages/<Name>.tsx. Add a page only after the new-page gate (prototype skill).
import { createHashRouter, Navigate, RouterProvider } from "react-router"

import { AppShell } from "@/components/AppShell"
import Home from "@/pages/Home"
import Settings from "@/pages/Settings"

const router = createHashRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <Home /> },
      { path: "settings", element: <Settings /> },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
