<script setup lang="ts">
import OSidebar from './OSidebar.vue'
import AppHeader from './AppHeader.vue'
</script>

<template>
  <div class="flex h-full min-h-0 overflow-hidden" data-portal="o">
    <OSidebar />
    <div class="flex-1 min-h-0 flex flex-col overflow-hidden">
      <AppHeader />
      <main class="surface-page-o flex-1 min-h-0 overflow-hidden">
        <router-view />
      </main>
    </div>
  </div>
</template>
