<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { useChatStore } from '../../stores/chat'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const chatStore = useChatStore()

const navItems = [
  {
    path: '/o/dashboard',
    label: '仪表盘',
    icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
  },
  {
    path: '/o/knowledge',
    label: '知识库运营',
    icon: 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253',
  },
  {
    path: '/o/traces',
    label: 'Trace 追踪',
    icon: 'M13 10V3L4 14h7v7l9-11h-7z',
  },
  {
    path: '/o/evolution',
    label: '自进化',
    icon: 'M4 4v6h6M20 20v-6h-6M5 19a9 9 0 0014-7M19 5A9 9 0 005 12',
  },
  {
    path: '/o/chat',
    label: '调试对话',
    icon: 'M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z',
  },
]

async function handleLogout() {
  await auth.logout()
  chatStore.clearChat()
  await router.replace('/login')
}
</script>

<template>
  <aside
    class="w-60 h-screen flex flex-col shrink-0 overflow-hidden bg-gradient-to-b from-slate-950 to-slate-900 text-slate-200 border-r border-indigo-300/10"
  >
    <div class="px-4 py-4 border-b border-indigo-300/10">
      <div class="flex items-center gap-2.5">
        <div
          class="w-9 h-9 bg-gradient-to-br from-indigo-500 to-indigo-600 rounded-xl flex items-center justify-center text-white font-bold shadow-sm"
        >
          O
        </div>
        <div class="min-w-0">
          <div class="text-sm font-semibold text-white leading-tight">MediZJ 运营端</div>
          <div class="text-[11px] text-slate-400 mt-0.5">平台管理与观测</div>
        </div>
      </div>
    </div>

    <nav class="px-3 pt-3 space-y-1 flex-1 overflow-y-auto scrollbar-thin">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="relative flex items-center gap-3 px-3 py-2.5 text-sm rounded-xl transition"
        :class="
          route.path.startsWith(item.path)
            ? 'bg-indigo-400/15 text-white font-medium'
            : 'text-slate-300 hover:bg-white/5 hover:text-white'
        "
      >
        <span
          v-if="route.path.startsWith(item.path)"
          class="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-indigo-400"
        />
        <svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" :d="item.icon" />
        </svg>
        {{ item.label }}
      </router-link>
    </nav>

    <div class="p-3 border-t border-indigo-300/10 space-y-2">
      <router-link
        to="/chat"
        class="flex items-center gap-3 px-3 py-2 text-sm rounded-xl transition text-slate-300 hover:bg-white/5 hover:text-white"
      >
        <svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="1.5"
            d="M11 17l-5-5 5-5m7 10l-5-5 5-5"
          />
        </svg>
        <span class="truncate">返回用户端</span>
      </router-link>

      <div class="rounded-xl bg-white/5 px-3 py-3 border border-white/5">
        <div class="text-sm text-white truncate">{{ auth.user?.username }}</div>
        <div
          class="mt-1 inline-flex rounded-full bg-indigo-400/15 px-1.5 py-0.5 text-[10px] font-medium text-indigo-200"
        >
          管理员
        </div>
        <button
          class="mt-3 w-full rounded-lg bg-white/10 py-1.5 text-xs text-slate-200 hover:bg-white/15 transition"
          @click="handleLogout"
        >
          退出登录
        </button>
      </div>
    </div>

    <div class="px-3 pb-3 text-xs text-slate-500">MediZJ Agent Swarm v0.1.0</div>
  </aside>
</template>
