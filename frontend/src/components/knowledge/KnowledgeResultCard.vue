<script setup lang="ts">
import { computed } from 'vue'
import type { KnowledgeCenterItem } from '../../types'

const props = defineProps<{ item: KnowledgeCenterItem }>()
defineEmits<{ preview: [docId: string]; continue: [docId: string] }>()
const docId = computed(() => String(props.item.metadata.doc_id || props.item.id))
const title = computed(() =>
  String(props.item.metadata.filename || props.item.metadata.disease || '健康知识'),
)
const source = computed(() => String(props.item.metadata.source || '来源未提供'))
const reviewedAt = computed(() =>
  String(props.item.metadata.reviewed_at || props.item.metadata.published_at || '来源时间未提供'),
)
</script>

<template>
  <article
    class="rounded-2xl border border-slate-200 bg-white px-4 py-5 shadow-sm transition hover:border-blue-200 hover:shadow-md sm:px-5"
  >
    <div class="flex items-start justify-between gap-4">
      <div class="min-w-0">
        <h2 class="text-base font-semibold text-slate-900">{{ title }}</h2>
        <p class="mt-1 text-xs text-slate-500">{{ source }} · {{ reviewedAt }}</p>
      </div>
      <span class="shrink-0 rounded-full bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-700"
        >相关度 {{ Math.round(item.score * 100) }}%</span
      >
    </div>
    <p class="mt-3 line-clamp-4 whitespace-pre-line text-sm leading-6 text-slate-700">
      {{ item.content }}
    </p>
    <div class="mt-4 flex flex-wrap gap-2">
      <button
        :data-preview-doc-id="docId"
        class="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700"
        @click="$emit('preview', docId)"
      >
        查看来源
      </button>
      <button
        class="rounded-lg bg-teal-50 px-3 py-1.5 text-sm font-medium text-teal-700 transition hover:bg-teal-100 hover:text-teal-900"
        @click="$emit('continue', docId)"
      >
        继续咨询
      </button>
    </div>
  </article>
</template>
