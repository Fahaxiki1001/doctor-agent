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
    label: '轨迹',
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
  <aside class="w-60 h-screen bg-slate-900 text-slate-200 flex flex-col shrink-0 overflow-hidden">
    <div class="p-4 border-b border-slate-700">
      <div class="flex items-center gap-2">
        <div
          class="w-8 h-8 bg-indigo-500 rounded-lg flex items-center justify-center text-white font-bold text-sm"
        >
          O
        </div>
        <div>
          <div class="text-sm font-semibold text-white">MediZJ 运营端</div>
          <div class="text-xs text-slate-400">平台管理与观测</div>
        </div>
      </div>
    </div>

    <nav class="px-3 pt-3 space-y-1 flex-1 overflow-y-auto scrollbar-thin">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="flex items-center gap-3 px-3 py-2.5 text-sm rounded-lg transition"
        :class="
          route.path.startsWith(item.path)
            ? 'bg-slate-700 text-white'
            : 'text-slate-300 hover:bg-slate-700/50 hover:text-white'
        "
      >
        <svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" :d="item.icon" />
        </svg>
        {{ item.label }}
      </router-link>
    </nav>

    <div class="p-3 border-t border-slate-700 space-y-2">
      <router-link
        to="/chat"
        class="flex items-center gap-3 px-3 py-2 text-sm rounded-lg transition text-slate-300 hover:bg-slate-700/50 hover:text-white"
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

      <div class="px-3 py-2 rounded-lg bg-slate-800">
        <div class="text-sm text-white truncate">{{ auth.user?.username }}</div>
        <div class="text-[10px] text-indigo-300 mt-0.5">管理员</div>
        <button
          class="mt-2 w-full py-1.5 text-xs text-slate-200 bg-slate-700 rounded hover:bg-slate-600 transition"
          @click="handleLogout"
        >
          退出登录
        </button>
      </div>
    </div>

    <div class="px-3 pb-3 text-xs text-slate-600">MediZJ Agent Swarm v0.1.0</div>
  </aside>
</template>
