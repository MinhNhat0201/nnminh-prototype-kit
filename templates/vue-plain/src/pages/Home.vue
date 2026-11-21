<script setup lang="ts">
import { RouterLink } from "vue-router"
import { items } from "@/lib/mock"

const APP_NAME = "{{APP_NAME}}"
</script>

<template>
  <section class="app-page">
    <h1>{{ APP_NAME }}</h1>
    <p>Start screen of the prototype. {{PAGE_NOTE}}</p>
    <div class="app-panel">
      <strong>Recent items</strong>
      <ul class="app-list">
        <li v-for="it in items" :key="it.id"><RouterLink to="/">{{ it.title }}</RouterLink></li>
      </ul>
    </div>
    <p><RouterLink to="/settings">Open settings</RouterLink></p>
  </section>
</template>
