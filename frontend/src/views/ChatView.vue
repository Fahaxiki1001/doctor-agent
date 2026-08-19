<script setup lang="ts">
import { computed, ref, nextTick, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useChatStore } from '../stores/chat'
import ChatInput from '../components/chat/ChatInput.vue'
import ChatMessage from '../components/chat/ChatMessage.vue'
import { shouldSuggestTriage } from '../utils/triageRouting'

const route = useRoute()
const router = useRouter()
const chatStore = useChatStore()
const messagesContainer = ref<HTMLElement | null>(null)
const triageSuggestion = ref('')

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

const initialQuestion = computed(() => String(route.query.ask || ''))

async function handleSend(question: string, images?: string[]) {
  if (shouldSuggestTriage(question)) triageSuggestion.value = question
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

function openTriage(symptom = '') {
  void router.push({
    name: 'Triage',
    query: symptom ? { symptom } : {},
  })
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
        <h2 class="text-2xl font-semibold text-slate-700 mb-2">健康咨询助手</h2>
        <p class="text-sm max-w-md text-center text-slate-500 leading-6">
          适合了解疾病知识、用药常识和日常健康管理，不替代诊断或线下就医。
        </p>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-2.5 mt-7 max-w-lg w-full">
          <button
            v-for="q in ['高血压患者饮食注意事项', '服用布洛芬有哪些注意事项', '怎样改善睡眠质量']"
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
        <button
          type="button"
          class="mt-4 flex w-full max-w-lg items-center justify-between gap-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-left transition hover:border-amber-300 hover:bg-amber-100/70"
          @click="openTriage()"
        >
          <span>
            <span class="block text-sm font-medium text-amber-950">正在经历身体不适？</span>
            <span class="mt-0.5 block text-xs text-amber-800">
              用症状分诊判断就医紧急度，通常约 2 分钟
            </span>
          </span>
          <span class="shrink-0 text-sm font-semibold text-amber-900">开始分诊 →</span>
        </button>
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

    <div
      v-if="triageSuggestion"
      class="shrink-0 border-t border-amber-100 bg-amber-50/80 px-4 py-3"
      aria-live="polite"
    >
      <div class="mx-auto flex max-w-3xl items-center gap-3">
        <div class="min-w-0 flex-1">
          <p class="text-sm font-medium text-amber-950">这是你当前正在经历的不适吗？</p>
          <p class="mt-0.5 text-xs text-amber-800">
            健康咨询会继续回答；如需判断是否应该就医，建议完成症状分诊。
          </p>
        </div>
        <button
          type="button"
          class="shrink-0 rounded-lg bg-amber-900 px-3 py-2 text-xs font-semibold text-white transition hover:bg-amber-800"
          @click="openTriage(triageSuggestion)"
        >
          开始分诊
        </button>
        <button
          type="button"
          class="shrink-0 p-1 text-amber-700 transition hover:text-amber-950"
          aria-label="关闭症状分诊提示"
          @click="triageSuggestion = ''"
        >
          ×
        </button>
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
