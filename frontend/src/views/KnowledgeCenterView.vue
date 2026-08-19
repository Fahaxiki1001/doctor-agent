<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import KnowledgeResultCard from '../components/knowledge/KnowledgeResultCard.vue'
import KnowledgeSearchBar from '../components/knowledge/KnowledgeSearchBar.vue'
import SourcePanel from '../components/knowledge/SourcePanel.vue'
import { useKnowledgeCenterStore } from '../stores/knowledgeCenter'

const store = useKnowledgeCenterStore()
const router = useRouter()
const route = useRoute()
const previewSourceId = ref('')

async function openPreview(docId: string) {
  previewSourceId.value = docId
  await store.openPreview(docId)
}

async function closePreview() {
  const docId = previewSourceId.value
  store.preview = null
  await nextTick()
  const trigger = Array.from(document.querySelectorAll('[data-preview-doc-id]')).find(
    (node) => node.getAttribute('data-preview-doc-id') === docId,
  )
  if (trigger instanceof HTMLElement) trigger.focus()
}

async function continueChat(docId: string) {
  const value = await store.continueChat(docId)
  if (!value) return
  sessionStorage.setItem('medizj_chat_context', JSON.stringify(value.context))
  await router.push({ name: 'Chat', query: { ask: store.query } })
}

onMounted(async () => {
  await store.loadCategories()
  const taskId = route.query.task_id
  if (typeof taskId === 'string') await store.restore(taskId)
})
</script>

<template>
  <div class="h-full overflow-y-auto bg-slate-50 pb-20 lg:pb-0">
    <KnowledgeSearchBar
      :query="store.query"
      :category="store.category"
      :categories="store.categories"
      :loading="store.loading"
      @update:query="store.query = $event"
      @update:category="store.category = $event"
      @search="store.search"
    />
    <main class="mx-auto max-w-4xl py-5 sm:px-6">
      <div
        v-if="store.error"
        role="alert"
        class="mx-4 border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 sm:mx-0"
      >
        {{ store.error }}
      </div>
      <div v-else-if="store.loading" class="py-16 text-center text-sm text-slate-500">
        正在检索可靠来源...
      </div>
      <div v-else-if="store.results.length" class="space-y-3 px-4 sm:px-0">
        <KnowledgeResultCard
          v-for="item in store.results"
          :key="String(item.metadata.doc_id || item.id)"
          :item="item"
          @preview="openPreview"
          @continue="continueChat"
        />
      </div>
      <div
        v-else
        class="mx-4 rounded-2xl border border-dashed border-slate-300 bg-white px-4 py-16 text-center sm:mx-0"
      >
        <span
          class="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-slate-100 text-slate-400"
        >
          <svg
            class="h-5 w-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="1.8"
              d="m21 21-4.3-4.3M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14Z"
            />
          </svg>
        </span>
        <p class="mt-3 text-sm font-medium text-slate-600">
          {{ store.searchId ? '没有找到达到相关度要求的来源' : '输入关键词开始检索健康知识' }}
        </p>
        <p class="mt-1 text-xs text-slate-400">系统只展示达到相关度要求的可信来源</p>
      </div>
    </main>
    <SourcePanel v-if="store.preview" :source="store.preview" @close="closePreview" />
  </div>
</template>
