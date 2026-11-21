<script setup lang="ts">
import { RouterLink } from "vue-router"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { items } from "@/lib/mock"

const APP_NAME = "{{APP_NAME}}"
</script>

<template>
  <h1 class="m-0 text-2xl font-semibold">{{ APP_NAME }}</h1>
  <p class="m-0 text-muted-foreground">Start screen of the prototype. Replace this content with DS components from the catalogue.</p>
  <Card>
    <CardHeader>
      <CardTitle>Recent items</CardTitle>
      <CardDescription>Mock data</CardDescription>
    </CardHeader>
    <CardContent>
      <ul class="m-0 flex list-none flex-col p-0">
        <li v-for="it in items" :key="it.id" class="border-t py-3 first:border-t-0">{{ it.title }}</li>
      </ul>
    </CardContent>
  </Card>
  <div>
    <Button as-child>
      <RouterLink to="/settings">Open settings</RouterLink>
    </Button>
  </div>
</template>
