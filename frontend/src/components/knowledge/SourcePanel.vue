<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { KnowledgeDocumentPreview } from '../../types'

defineProps<{ source: KnowledgeDocumentPreview }>()
defineEmits<{ close: [] }>()

const closeButton = ref<HTMLElement | null>(null)

onMounted(() => closeButton.value?.focus())
</script>

<template>
  <aside
    class="fixed inset-0 z-40 flex justify-end bg-black/25"
    role="dialog"
    aria-modal="true"
    aria-label="知识来源详情"
    @click.self="$emit('close')"
    @keydown.esc="$emit('close')"
  >
    <div class="h-full w-full max-w-xl overflow-y-auto bg-white p-5 shadow-xl sm:p-7">
      <div class="flex items-start justify-between gap-4">
        <div>
          <h2 class="text-lg font-semibold text-slate-900">{{ source.title }}</h2>
          <p class="mt-1 text-sm text-slate-500">{{ source.source || '来源未提供' }}</p>
        </div>
        <button
          ref="closeButton"
          type="button"
          class="rounded p-1 text-slate-500 hover:bg-slate-100"
          title="关闭"
          aria-label="关闭来源详情"
          @click="$emit('close')"
        >
          <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-width="2" d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      </div>
      <dl class="mt-5 grid grid-cols-2 gap-x-4 gap-y-3 border-y border-slate-200 py-4 text-sm">
        <div>
          <dt class="text-slate-500">更新时间</dt>
          <dd class="mt-1 text-slate-800">
            {{ source.reviewed_at || source.published_at || '来源时间未提供' }}
          </dd>
        </div>
        <div>
          <dt class="text-slate-500">适用人群</dt>
          <dd class="mt-1 text-slate-800">{{ source.applicable_population || '未提供' }}</dd>
        </div>
      </dl>
      <div class="mt-5 whitespace-pre-line text-sm leading-7 text-slate-700">
        {{ source.content }}
      </div>
    </div>
  </aside>
</template>
