<script setup lang="ts">
defineProps<{
  query: string
  category: string
  categories: Array<{ key: string; label: string; description: string }>
  loading?: boolean
}>()
const emit = defineEmits<{
  'update:query': [value: string]
  'update:category': [value: string]
  search: []
}>()
</script>

<template>
  <form
    class="border-b border-slate-200 bg-white px-4 py-5 sm:px-6 sm:py-6"
    @submit.prevent="emit('search')"
  >
    <div class="mx-auto max-w-4xl">
      <div class="flex flex-col gap-3 sm:flex-row">
        <label class="sr-only" for="knowledge-query">搜索健康知识</label>
        <div class="relative flex-1">
          <svg
            class="pointer-events-none absolute left-3.5 top-3 h-5 w-5 text-slate-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="m21 21-4.3-4.3M11 18a7 7 0 100-14 7 7 0 000 14z"
            />
          </svg>
          <input
            id="knowledge-query"
            :value="query"
            maxlength="500"
            class="h-11 w-full rounded-xl border border-slate-200 bg-slate-50 pl-11 pr-3 text-sm shadow-sm transition placeholder:text-slate-400 hover:border-slate-300 hover:bg-white focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-4 focus:ring-blue-100/70"
            placeholder="搜索疾病、症状、检查指标或生活方式"
            @input="emit('update:query', ($event.target as HTMLInputElement).value)"
          />
        </div>
        <button
          type="submit"
          :disabled="loading || !query.trim()"
          class="h-11 shrink-0 rounded-xl bg-blue-600 px-6 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 hover:shadow disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none"
        >
          {{ loading ? '检索中...' : '搜索' }}
        </button>
      </div>

      <fieldset class="mt-4">
        <legend class="mb-2 text-xs font-medium text-slate-500">按内容分类筛选</legend>
        <div class="flex flex-wrap gap-2">
          <button
            type="button"
            class="rounded-full border px-3.5 py-1.5 text-sm font-medium transition"
            :class="
              !category
                ? 'border-blue-600 bg-blue-600 text-white shadow-sm'
                : 'border-slate-200 bg-white text-slate-600 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700'
            "
            :aria-pressed="!category"
            @click="emit('update:category', '')"
          >
            全部
          </button>
          <button
            v-for="item in categories"
            :key="item.key"
            type="button"
            class="rounded-full border px-3.5 py-1.5 text-sm font-medium transition"
            :class="
              category === item.key
                ? 'border-blue-600 bg-blue-600 text-white shadow-sm'
                : 'border-slate-200 bg-white text-slate-600 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700'
            "
            :aria-pressed="category === item.key"
            :title="item.description"
            @click="emit('update:category', item.key)"
          >
            {{ item.label }}
          </button>
        </div>
      </fieldset>
    </div>
  </form>
</template>
