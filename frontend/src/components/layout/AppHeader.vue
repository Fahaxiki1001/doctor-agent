<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useChatStore } from '../../stores/chat'

const route = useRoute()
const chatStore = useChatStore()

const pageTitles: Record<string, string> = {
  Chat: '智能问答',
  OChat: '调试对话',
  Knowledge: '知识库运营',
  Dashboard: '仪表盘',
  Traces: '轨迹',
  TraceDetail: '轨迹详情',
  Personal: '个人中心',
}

const title = computed(() => {
  const name = route.name as string
  if (name === 'ChatSession') {
    return chatStore.sessionTitle || '智能问答'
  }
  return pageTitles[name] || 'MediZJ'
})

const portalLabel = computed(() => (route.meta.portal === 'o' ? '运营端' : '用户端'))
</script>

<template>
  <header
    class="h-14 bg-white border-b border-slate-200 flex items-center justify-between px-6 shrink-0"
  >
    <h1 class="text-lg font-semibold text-slate-800">{{ title }}</h1>
    <span class="text-xs text-slate-400">{{ portalLabel }}</span>
  </header>
</template>
