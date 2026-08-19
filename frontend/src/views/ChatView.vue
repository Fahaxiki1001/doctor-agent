<script setup lang="ts">
import { computed, ref, nextTick, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useChatStore } from '../stores/chat'
import ChatInput from '../components/chat/ChatInput.vue'
import ChatMessage from '../components/chat/ChatMessage.vue'

const route = useRoute()
const router = useRouter()
const chatStore = useChatStore()
const messagesContainer = ref<HTMLElement | null>(null)

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

const initialQuestion = computed(() => String(route.query.ask || ''))

async function handleSend(question: string, images?: string[]) {
  let context: Record<string, unknown> | undefined
  const rawContext = sessionStorage.getItem('medizj_chat_context')
  if (rawContext) {
    try {
      context = JSON.parse(rawContext)
    } catch {
      context = undefined
    }
    sessionStorage.removeItem('medizj_chat_context')
  }
  await chatStore.sendMessage(question, images, context)
  if (route.query.ask) await router.replace({ name: 'Chat' })
  scrollToBottom()
}

watch(() => chatStore.messages.length, scrollToBottom)

onMounted(() => {
  const sessionId = route.params.sessionId as string
  if (sessionId) {
    chatStore.loadHistory(sessionId)
  }
})

// 路由参数变化时重新加载（如点击侧边栏另一个会话）
watch(
  () => route.params.sessionId,
  (newId, oldId) => {
    if (newId && newId !== oldId) {
      chatStore.clearChat()
      chatStore.loadHistory(newId as string)
    }
  },
)
</script>

<template>
  <div class="flex flex-col h-full min-h-0 overflow-hidden">
    <!-- 消息列表 -->
    <div ref="messagesContainer" class="flex-1 min-h-0 overflow-y-auto overscroll-contain">
      <!-- 空状态 -->
      <div
        v-if="chatStore.messages.length === 0"
        class="h-full flex flex-col items-center justify-center text-slate-400 px-4"
      >
        <div class="w-20 h-20 mb-5 rounded-full bg-blue-50 flex items-center justify-center">
          <svg
            class="w-10 h-10 text-blue-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="1.5"
              d="M9 12h.01M15 12h.01M12 3a9 9 0 100 18 9 9 0 000-18zM9 16s1.5 2 3 2 3-2 3-2"
            />
          </svg>
        </div>
        <h2 class="text-2xl font-semibold text-slate-700 mb-2">MediZJ 医疗助手</h2>
        <p class="text-sm max-w-sm text-center text-slate-500">
          请输入您的健康问题，我们将为您提供专业的咨询建议。
        </p>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-2.5 mt-7 max-w-lg w-full">
          <button
            v-for="q in ['高血压患者饮食注意事项', '头疼发烧是怎么回事', '糖尿病最新临床指南']"
            :key="q"
            @click="handleSend(q)"
            class="flex items-center gap-2 text-left text-xs px-3 py-3 bg-white border border-slate-200 rounded-xl shadow-sm hover:border-blue-300 hover:shadow-md hover:-translate-y-px hover:text-blue-600 transition-all"
          >
            <svg
              class="w-4 h-4 shrink-0 text-blue-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="1.5"
                d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
              />
            </svg>
            <span>{{ q }}</span>
          </button>
        </div>
      </div>

      <!-- 消息列表 -->
      <div v-else>
        <ChatMessage
          v-for="(msg, index) in chatStore.messages"
          :key="msg.id"
          :message="msg"
          :show-disclaimer="
            msg.role === 'assistant' && index === chatStore.messages.length - 1 && !msg.isStreaming
          "
        />
      </div>
    </div>

    <!-- 输入框 -->
    <ChatInput
      class="shrink-0"
      :disabled="chatStore.isStreaming"
      :initial-value="initialQuestion"
      @send="handleSend"
    />
  </div>
</template>
