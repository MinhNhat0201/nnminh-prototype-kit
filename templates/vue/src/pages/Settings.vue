<script setup lang="ts">
import { ref } from "vue"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
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
  <h1 class="m-0 text-2xl font-semibold">Settings</h1>
  <Card>
    <CardHeader>
      <CardTitle>Appearance</CardTitle>
      <CardDescription>Theming attributes from ds.json &gt; theming, saved in this browser only.</CardDescription>
    </CardHeader>
    <CardContent class="flex flex-col gap-4">
      <label v-for="[key, t] in axes" :key="key" class="flex max-w-xs flex-col gap-1 text-sm">
        <span class="capitalize">{{ key }}</span>
        <select class="rounded-md border border-input bg-background p-2 text-foreground" :value="values[key]" @change="change(key, $event)">
          <option v-for="v in t.values" :key="v" :value="v">{{ v }}</option>
        </select>
      </label>
    </CardContent>
  </Card>
</template>
