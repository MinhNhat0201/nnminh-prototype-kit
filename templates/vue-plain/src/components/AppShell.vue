<script setup lang="ts">
// App shell: top bar, navigation rail (medium and wider) <-> bottom tab bar (compact), footer with the version label.
// Skeleton classes app-* live in src/index.css. {{SHELL_NOTE}}
import { RouterLink, RouterView } from "vue-router"
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
  <div class="app">
    <header class="app-top">
      <span class="app-brand">{{ APP_NAME }}</span>
      <button v-if="canToggle" class="app-icon-btn" type="button" aria-label="Switch light or dark mode" title="Light or dark mode" @click="toggleMode">
        <NavIcon name="mode" />
      </button>
    </header>

    <nav class="app-nav" aria-label="Main">
      <RouterLink v-for="n in NAV" :key="n.to" :to="n.to">
        <NavIcon :name="n.icon" />
        <span>{{ n.label }}</span>
      </RouterLink>
    </nav>

    <main class="app-main">
      <RouterView />
    </main>

    <footer class="app-foot">
      <span>{{ APP_NAME }} · prototype · <span data-mock="true">mock data</span></span>
      <span class="app-version">{{ label }}</span>
    </footer>
  </div>
</template>
