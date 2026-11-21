<script setup lang="ts">
import { ref } from "vue"
import { THEMING, getTheming, setTheming } from "@/lib/theming"

const axes = Object.entries(THEMING).filter(([, t]) => t?.attr && (t.values?.length ?? 0) > 1)
const values = ref<Record<string, string | undefined>>(Object.fromEntries(axes.map(([k]) => [k, getTheming(k)])))

function change(key: string, e: Event) {
  const v = (e.target as HTMLSelectElement).value
  setTheming(key, v)
  values.value[key] = v
}
</script>

<template>
  <section class="app-page">
    <h1>Settings</h1>
    <p>Theming attributes from ds.json &gt; theming, saved in this browser only.</p>
    <div class="app-panel">
      <label v-for="[key, t] in axes" :key="key" class="app-field">
        <span>{{ key }}</span>
        <select :value="values[key]" @change="change(key, $event)">
          <option v-for="v in t.values" :key="v" :value="v">{{ v }}</option>
        </select>
      </label>
    </div>
  </section>
</template>
