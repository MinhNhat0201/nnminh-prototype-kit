// Hash history router: the static build opens from a folder; #/ is home; unknown paths go home; Back/Forward work.
// One route per page; pages live in src/pages/<Name>.vue. Add a page only after the new-page gate (prototype skill).
import { createRouter, createWebHashHistory } from "vue-router"
import Home from "@/pages/Home.vue"
import Settings from "@/pages/Settings.vue"

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", component: Home },
    { path: "/settings", component: Settings },
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
  scrollBehavior: () => ({ top: 0 }),
})
