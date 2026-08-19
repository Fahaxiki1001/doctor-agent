<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { deleteHealthTask, getHealthTasks, submitHealthTaskFeedback } from '../../api/tasks'
import type { HealthTask, HealthTaskType } from '../../types'

const router = useRouter()
const tasks = ref<HealthTask[]>([])
const loading = ref(false)
const filter = ref<HealthTaskType | ''>('')
const statusFilter = ref<HealthTask['status'] | ''>('')
const feedback = ref<Record<string, 'like' | 'dislike'>>({})
const feedbackSaving = ref<string | null>(null)

const visible = computed(() =>
  tasks.value.filter(
    (task) =>
      (!filter.value || task.task_type === filter.value) &&
      (!statusFilter.value || task.status === statusFilter.value),
  ),
)
const typeLabel = {
  triage: '症状自测',
  knowledge_search: '知识搜索',
  report_interpretation: '报告解读',
}
const statusLabel: Record<string, string> = {
  created: '已创建',
  collecting: '待补充',
  processing: '处理中',
  waiting_confirmation: '待确认',
  completed: '已完成',
  needs_medical_attention: '需就医',
  failed: '失败',
  cancelled: '已取消',
}
const statusClass: Record<string, string> = {
  created: 'bg-slate-100 text-slate-600',
  collecting: 'bg-amber-50 text-amber-700',
  processing: 'bg-blue-50 text-blue-700',
  waiting_confirmation: 'bg-amber-50 text-amber-700',
  completed: 'bg-emerald-50 text-emerald-700',
  needs_medical_attention: 'bg-red-50 text-red-700',
  failed: 'bg-red-50 text-red-700',
  cancelled: 'bg-slate-100 text-slate-500',
}
const selectClass =
  'h-10 w-full appearance-none rounded-xl border border-slate-200 bg-white py-2 pl-3 pr-9 text-sm font-medium text-slate-700 shadow-sm transition hover:border-slate-300 focus:border-blue-500 focus:outline-none focus:ring-4 focus:ring-blue-100/70'

async function load() {
  loading.value = true
  try {
    tasks.value = (await getHealthTasks({ limit: 100 })).tasks
  } finally {
    loading.value = false
  }
}

function summary(task: HealthTask) {
  if (task.task_type === 'triage')
    return String(task.result.urgency || task.input_snapshot.symptom || '症状自测')
  if (task.task_type === 'knowledge_search')
    return String(task.result.query || task.input_snapshot.query || '知识搜索')
  return `报告任务 · ${statusLabel[task.status] || task.status}`
}

async function open(task: HealthTask) {
  if (task.task_type === 'triage') return router.push(`/triage/${task.task_id}`)
  if (task.task_type === 'report_interpretation' && task.input_snapshot.report_id) {
    return router.push(`/reports/${String(task.input_snapshot.report_id)}`)
  }
  return router.push({ path: '/knowledge', query: { task_id: task.task_id } })
}

async function remove(task: HealthTask, event: Event) {
  event.stopPropagation()
  if (!confirm('确定删除这条健康任务记录？')) return
  await deleteHealthTask(task.task_id)
  tasks.value = tasks.value.filter((item) => item.task_id !== task.task_id)
}

async function rate(task: HealthTask, rating: 'like' | 'dislike', event: Event) {
  event.stopPropagation()
  if (feedbackSaving.value === task.task_id) return
  feedbackSaving.value = task.task_id
  try {
    await submitHealthTaskFeedback(task.task_id, rating)
    feedback.value[task.task_id] = rating
  } finally {
    feedbackSaving.value = null
  }
}

onMounted(load)
</script>

<template>
  <section class="rounded-2xl border border-slate-200 bg-slate-50/60 p-4 sm:p-5">
    <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-lg font-semibold text-slate-800">健康任务记录</h2>
        <p class="mt-1 text-sm text-slate-500">自测、知识搜索和报告解读可在这里再次查看</p>
      </div>
      <div class="grid w-full grid-cols-2 gap-2 sm:w-auto">
        <div class="relative min-w-0 sm:w-36">
          <select v-model="filter" :class="selectClass" aria-label="按类型筛选健康任务">
            <option value="">全部类型</option>
            <option value="triage">症状自测</option>
            <option value="knowledge_search">知识搜索</option>
            <option value="report_interpretation">报告解读</option>
          </select>
          <svg
            class="pointer-events-none absolute right-3 top-3 h-4 w-4 text-slate-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="m8 10 4 4 4-4"
            />
          </svg>
        </div>
        <div class="relative min-w-0 sm:w-36">
          <select v-model="statusFilter" :class="selectClass" aria-label="按状态筛选健康任务">
            <option value="">全部状态</option>
            <option value="collecting">待补充</option>
            <option value="processing">处理中</option>
            <option value="waiting_confirmation">待确认</option>
            <option value="completed">已完成</option>
            <option value="needs_medical_attention">需就医</option>
            <option value="failed">失败</option>
            <option value="cancelled">已取消</option>
          </select>
          <svg
            class="pointer-events-none absolute right-3 top-3 h-4 w-4 text-slate-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="m8 10 4 4 4-4"
            />
          </svg>
        </div>
      </div>
    </div>
    <div
      v-if="loading"
      class="rounded-xl border border-slate-200 bg-white py-8 text-center text-sm text-slate-500"
    >
      加载中...
    </div>
    <div
      v-else-if="!visible.length"
      class="rounded-xl border border-dashed border-slate-300 bg-white py-8 text-center text-sm text-slate-500"
    >
      暂无健康任务
    </div>
    <div v-else class="space-y-2">
      <div
        v-for="task in visible"
        :key="task.task_id"
        class="group flex w-full items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-3 text-left shadow-sm transition hover:border-blue-200 hover:shadow sm:gap-3"
      >
        <button
          type="button"
          class="flex min-w-0 flex-1 items-center gap-2 rounded-sm text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 sm:gap-3"
          @click="open(task)"
        >
          <span class="min-w-0 flex-1">
            <span class="flex flex-wrap items-center gap-1.5">
              <span class="text-xs font-medium text-slate-500">{{
                typeLabel[task.task_type]
              }}</span>
              <span
                class="rounded-full px-2 py-0.5 text-[11px] font-semibold"
                :class="statusClass[task.status] || 'bg-slate-100 text-slate-600'"
              >
                {{ statusLabel[task.status] || task.status }}
              </span>
            </span>
            <span class="mt-1.5 block truncate text-sm font-medium text-slate-800">{{
              summary(task)
            }}</span>
          </span>
          <span class="shrink-0 text-xs text-slate-400">{{
            new Date(task.created_at).toLocaleDateString('zh-CN')
          }}</span>
        </button>
        <span
          v-if="['completed', 'needs_medical_attention'].includes(task.status)"
          class="flex shrink-0 items-center gap-1"
          role="group"
          aria-label="结果反馈"
        >
          <button
            class="p-1 text-slate-400 hover:text-emerald-700 disabled:opacity-50"
            :class="{ 'text-emerald-700': feedback[task.task_id] === 'like' }"
            :disabled="feedbackSaving === task.task_id"
            title="有帮助"
            aria-label="这条结果有帮助"
            @click="rate(task, 'like', $event)"
          >
            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M7 10v10H4V10h3Zm0 9h9.3a2 2 0 0 0 1.9-1.4l1.5-5A2 2 0 0 0 17.8 10H14l.7-3.2A2.3 2.3 0 0 0 10.3 5L7 10"
              />
            </svg>
          </button>
          <button
            class="p-1 text-slate-400 hover:text-amber-700 disabled:opacity-50"
            :class="{ 'text-amber-700': feedback[task.task_id] === 'dislike' }"
            :disabled="feedbackSaving === task.task_id"
            title="需改进"
            aria-label="这条结果需要改进"
            @click="rate(task, 'dislike', $event)"
          >
            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M7 14V4H4v10h3Zm0-9h9.3a2 2 0 0 1 1.9 1.4l1.5 5a2 2 0 0 1-1.9 2.6H14l.7 3.2a2.3 2.3 0 0 1-4.4 1.8L7 14"
              />
            </svg>
          </button>
        </span>
        <button
          type="button"
          class="shrink-0 p-1 text-slate-400 opacity-100 hover:text-red-700 sm:opacity-0 sm:group-hover:opacity-100"
          title="删除任务"
          aria-label="删除任务"
          @click="remove(task, $event)"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-width="2" d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      </div>
    </div>
  </section>
</template>
