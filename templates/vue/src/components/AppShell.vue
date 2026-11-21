<script setup lang="ts">
// App shell: top bar, navigation rail (medium and wider) <-> bottom tab bar (compact), footer with the version label.
// When catalog.md > components.map lists shell components (top bar, navigation rail, tab bar), use them instead.
import { RouterLink, RouterView } from "vue-router"
import { Button } from "@/components/ui/button"
import NavIcon from "@/components/NavIcon.vue"
import { THEMING, toggleMode, versionLabel } from "@/lib/theming"

const APP_NAME = "{{APP_NAME}}"
const NAV = [
  { to: "/", label: "Home", icon: "home" as const },
  { to: "/settings", label: "Settings", icon: "settings" as const },
]
const canToggle = (THEMING.mode?.values?.length ?? 0) > 1
const label = versionLabel()
</script>

<template>
  <div class="grid min-h-dvh grid-cols-1 grid-rows-[auto_1fr_auto] medium:grid-cols-[auto_minmax(0,1fr)]">
    <header class="sticky top-0 z-10 flex min-h-14 items-center gap-3 border-b bg-background px-4 medium:col-span-2">
      <span class="mr-auto truncate font-semibold">{{ APP_NAME }}</span>
      <Button v-if="canToggle" variant="outline" size="icon" aria-label="Switch light or dark mode" title="Light or dark mode" @click="toggleMode">
        <NavIcon name="mode" />
      </Button>
    </header>

    <nav
      aria-label="Main"
      class="app-tabbar fixed inset-x-0 bottom-0 z-10 flex justify-around gap-1 border-t border-sidebar-border bg-sidebar px-2 pt-1 text-sidebar-foreground medium:static medium:row-span-2 medium:flex-col medium:justify-start medium:border-t-0 medium:border-r medium:p-2"
    >
      <RouterLink
        v-for="n in NAV"
        :key="n.to"
        :to="n.to"
        class="flex min-w-0 flex-1 flex-col items-center gap-1 rounded-md px-1 py-2 text-xs no-underline hover:bg-sidebar-accent hover:text-sidebar-accent-foreground medium:min-w-18 medium:flex-none"
        exact-active-class="bg-sidebar-primary text-sidebar-primary-foreground"
      >
        <NavIcon :name="n.icon" />
        <span>{{ n.label }}</span>
      </RouterLink>
    </nav>

    <main class="min-w-0 p-4 medium:p-6">
      <div class="mx-auto flex max-w-5xl flex-col gap-4">
        <RouterView />
      </div>
    </main>

    <footer class="flex flex-wrap justify-between gap-2 border-t px-6 pt-3 pb-20 text-xs text-muted-foreground medium:pb-3">
      <span>{{ APP_NAME }} · prototype · <span data-mock="true">mock data</span></span>
      <span class="app-version">{{ label }}</span>
    </footer>
  </div>
</template>
