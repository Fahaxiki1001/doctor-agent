<script setup lang="ts">
import CSidebar from './CSidebar.vue'
import AppHeader from './AppHeader.vue'
</script>

<template>
  <div class="flex h-full min-h-0 overflow-hidden" data-portal="c">
    <div class="hidden lg:block"><CSidebar /></div>
    <div class="flex-1 min-h-0 flex flex-col overflow-hidden">
      <AppHeader />
      <main class="surface-page flex-1 min-h-0 overflow-hidden">
        <router-view />
      </main>
    </div>
    <nav
      class="fixed inset-x-0 bottom-0 z-30 grid h-16 grid-cols-5 border-t border-slate-200 bg-white lg:hidden"
      aria-label="用户端主导航"
    >
      <router-link
        v-for="item in [
          { to: '/chat', label: '问健康' },
          { to: '/triage', label: '自测' },
          { to: '/knowledge', label: '知识' },
          { to: '/reports', label: '报告' },
          { to: '/personal', label: '我的' },
        ]"
        :key="item.to"
        :to="item.to"
        class="flex items-center justify-center px-1 text-xs text-slate-600"
        active-class="font-semibold text-blue-700"
      >
        {{ item.label }}
      </router-link>
    </nav>
  </div>
</template>
