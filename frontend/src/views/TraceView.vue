<template>
  <div class="surface-page-o h-full overflow-y-auto p-4 sm:p-6">
    <div class="mx-auto max-w-7xl space-y-6">
      <!-- Loading -->
      <div v-if="loading" class="text-center py-12 text-slate-400">加载中...</div>

      <!-- Error -->
      <div v-else-if="error" class="text-center py-12">
        <p class="text-red-500 mb-3">{{ error }}</p>
        <button @click="refresh" class="text-sm text-blue-500 hover:underline">重试</button>
      </div>

      <!-- 详情模式 -->
      <template v-else-if="selectedTraceId">
        <!-- 返回栏 -->
        <div class="flex items-center gap-4">
          <button
            @click="selectedTraceId = null"
            class="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 transition"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M15 19l-7-7 7-7"
              />
            </svg>
            返回列表
          </button>
          <span class="text-xs text-slate-400 font-mono"
            >{{ selectedTraceId.slice(0, 20) }}...</span
          >
        </div>

        <TraceWaterfall
          :spans="waterfallSpans"
          :totalDurationMs="waterfallTotalMs"
          :firstTokenTimeMs="waterfallFirstTokenMs"
          :selectedSpanId="selectedSpan?.id ?? null"
          @select-span="selectTopSpan"
        />
        <div class="grid grid-cols-1 gap-6">
          <SpanDetail
            v-if="selectedSpan"
            :span="selectedSpan"
            :allSpans="waterfallSpans"
            :canGoBack="spanNavStack.length > 1"
            @close="closeSpanDetail"
            @back="goBack"
            @select-span="navigateToChild"
          />
          <div
            v-else
            class="bg-white border border-slate-200 rounded-xl p-5 flex items-center justify-center"
          >
            <p class="text-sm text-slate-400">点击 waterfall 节点查看详情</p>
          </div>
        </div>
      </template>

      <!-- 列表 + 统计模式 -->
      <template v-else>
        <TraceStats
          :agentStats="agentStats"
          :toolStats="toolStats"
          :llmStats="llmStats"
          :slowTraces="slowTraces"
          :agentDays="7"
          :slowDays="7"
          @select-trace="selectedTraceId = $event"
        />

        <section class="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div class="flex items-center justify-between gap-4 border-b border-slate-100 px-5 py-4">
            <div>
              <div class="flex items-center gap-2">
                <h2 class="text-sm font-semibold text-slate-800">健康任务筛选</h2>
                <span
                  v-if="activeFilterCount"
                  class="rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-700"
                >
                  {{ activeFilterCount }} 项条件
                </span>
              </div>
              <p class="mt-1 text-xs text-slate-400">按任务状态和安全决策快速定位异常链路</p>
            </div>
            <button
              v-if="activeFilterCount"
              type="button"
              class="shrink-0 text-xs font-medium text-slate-500 transition hover:text-indigo-700"
              @click="clearFilters"
            >
              重置条件
            </button>
          </div>
          <form
            class="grid gap-4 p-5 sm:grid-cols-2 xl:grid-cols-4"
            aria-label="Trace 筛选"
            @submit.prevent="applyFilters"
          >
            <label class="block min-w-0">
              <span class="mb-1.5 block text-xs font-medium text-slate-500">任务类型</span>
              <span class="relative block">
                <select v-model="filters.task_type" :class="selectClass" aria-label="任务类型">
                  <option value="">全部任务类型</option>
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
              </span>
            </label>
            <label class="block min-w-0">
              <span class="mb-1.5 block text-xs font-medium text-slate-500">任务状态</span>
              <span class="relative block">
                <select v-model="filters.task_status" :class="selectClass" aria-label="任务状态">
                  <option value="">全部任务状态</option>
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
              </span>
            </label>
            <label class="block min-w-0">
              <span class="mb-1.5 block text-xs font-medium text-slate-500">安全决策</span>
              <span class="relative block">
                <select
                  v-model="filters.safety_decision"
                  :class="selectClass"
                  aria-label="安全决策"
                >
                  <option value="">全部安全决策</option>
                  <option value="allow">允许</option>
                  <option value="allow_with_notice">附提示</option>
                  <option value="medical_attention">需就医</option>
                  <option value="emergency_stop">紧急停止</option>
                  <option value="manual_review">人工复核</option>
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
              </span>
            </label>
            <label class="block min-w-0">
              <span class="mb-1.5 block text-xs font-medium text-slate-500">错误码</span>
              <input
                v-model.trim="filters.error_code"
                class="h-10 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 text-sm text-slate-700 shadow-sm transition placeholder:text-slate-400 hover:border-slate-300 focus:border-indigo-500 focus:bg-white focus:outline-none focus:ring-4 focus:ring-indigo-100/70"
                maxlength="80"
                placeholder="例如 KB_UNAVAILABLE"
              />
            </label>
            <div class="flex items-center justify-end gap-2 sm:col-span-2 xl:col-span-4">
              <button
                v-if="activeFilterCount"
                class="h-10 rounded-xl border border-slate-200 bg-white px-4 text-sm font-medium text-slate-600 transition hover:bg-slate-50"
                type="button"
                @click="clearFilters"
              >
                清空
              </button>
              <button
                class="h-10 rounded-xl bg-indigo-600 px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700 disabled:cursor-wait disabled:bg-indigo-300"
                type="submit"
                :disabled="listLoading"
              >
                {{ listLoading ? '筛选中...' : '应用筛选' }}
              </button>
            </div>
          </form>
        </section>

        <!-- Trace 列表 -->
        <div
          class="relative overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
        >
          <div
            class="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-5 py-3.5"
          >
            <div>
              <span class="text-sm font-semibold text-slate-800">最近 Trace</span>
              <span class="ml-2 text-xs text-slate-400">共 {{ totalTraces }} 条</span>
            </div>
            <button
              type="button"
              class="rounded-lg p-1.5 text-slate-400 transition hover:bg-white hover:text-indigo-600"
              aria-label="刷新 Trace 列表"
              title="刷新列表"
              :disabled="listLoading"
              @click="loadFilteredList"
            >
              <svg
                class="h-4 w-4"
                :class="{ 'animate-spin': listLoading }"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7"
                />
              </svg>
            </button>
          </div>
          <div v-if="traces.length" class="overflow-x-auto">
            <table class="w-full min-w-[860px] text-sm">
              <thead>
                <tr class="border-b border-slate-100 bg-white text-xs font-medium text-slate-500">
                  <th class="px-5 py-3 text-left">Trace / 时间</th>
                  <th class="px-4 py-3 text-left">问题摘要</th>
                  <th class="px-4 py-3 text-left">健康任务</th>
                  <th class="px-4 py-3 text-center">模式</th>
                  <th class="px-4 py-3 text-right">性能</th>
                  <th class="px-5 py-3 text-right">Tokens</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="t in traces"
                  :key="t.trace_id"
                  role="button"
                  tabindex="0"
                  class="cursor-pointer border-b border-slate-100 transition last:border-0 hover:bg-indigo-50/40 focus-visible:bg-indigo-50"
                  @click="selectedTraceId = t.trace_id"
                  @keydown.enter.prevent="selectedTraceId = t.trace_id"
                  @keydown.space.prevent="selectedTraceId = t.trace_id"
                >
                  <td class="px-5 py-3.5">
                    <span class="block font-mono text-xs font-medium text-slate-600">{{
                      t.trace_id.slice(0, 12)
                    }}</span>
                    <span class="mt-1 block whitespace-nowrap text-[11px] text-slate-400">{{
                      formatTime(t.start_time)
                    }}</span>
                  </td>
                  <td class="max-w-[300px] px-4 py-3.5">
                    <span class="block truncate text-sm font-medium text-slate-700">{{
                      t.question_summary || '无问题摘要'
                    }}</span>
                    <span
                      v-if="t.error_code"
                      class="mt-1 inline-flex rounded bg-red-50 px-1.5 py-0.5 font-mono text-[10px] text-red-700"
                      >{{ t.error_code }}</span
                    >
                  </td>
                  <td class="px-4 py-3.5 text-xs">
                    <template v-if="t.task_type">
                      <span class="font-medium text-slate-700">{{
                        taskTypeLabel(t.task_type)
                      }}</span>
                      <span
                        v-if="t.task_status"
                        class="ml-1.5 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600"
                        >{{ taskStatusLabel(t.task_status) }}</span
                      >
                      <span
                        v-if="t.safety_decision"
                        class="mt-1.5 block w-fit rounded-full px-2 py-0.5 text-[11px] font-medium"
                        :class="safetyDecisionClass(t.safety_decision)"
                        >{{ safetyDecisionLabel(t.safety_decision) }}</span
                      >
                    </template>
                    <span v-else class="text-slate-300">普通会话</span>
                  </td>
                  <td class="px-4 py-3.5 text-center">
                    <span
                      class="rounded-full px-2.5 py-1 text-xs font-medium"
                      :class="modeBadge(t.mode)"
                      >{{ modeLabel(t.mode) }}</span
                    >
                  </td>
                  <td class="px-4 py-3.5 text-right">
                    <span
                      class="block text-xs font-semibold tabular-figures"
                      :class="
                        (t.first_token_time_ms ?? 0) > 30000 ? 'text-amber-600' : 'text-slate-700'
                      "
                    >
                      {{
                        t.first_token_time_ms != null
                          ? (t.first_token_time_ms / 1000).toFixed(1) + 's'
                          : '暂无'
                      }}
                    </span>
                    <span class="mt-1 block text-[11px] text-slate-400"
                      >{{ t.span_count }} spans</span
                    >
                  </td>
                  <td class="px-5 py-3.5 text-right font-medium tabular-figures text-slate-600">
                    {{ t.total_tokens.toLocaleString() }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="py-12 text-center text-sm text-slate-400">
            暂无 trace 数据。发送一条消息后将自动生成。
          </div>
          <div
            v-if="totalTraces > pageSize"
            class="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 bg-slate-50 px-5 py-3"
          >
            <span class="text-xs text-slate-400">
              显示 {{ pageStart }}–{{ pageEnd }}，共 {{ totalTraces }} 条
            </span>
            <div class="flex items-center gap-2">
              <button
                type="button"
                class="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:border-indigo-200 hover:text-indigo-700 disabled:cursor-not-allowed disabled:opacity-40"
                :disabled="currentPage <= 1 || listLoading"
                @click="changePage(currentPage - 1)"
              >
                上一页
              </button>
              <span class="min-w-16 text-center text-xs text-slate-500">
                {{ currentPage }} / {{ totalPages }}
              </span>
              <button
                type="button"
                class="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:border-indigo-200 hover:text-indigo-700 disabled:cursor-not-allowed disabled:opacity-40"
                :disabled="currentPage >= totalPages || listLoading"
                @click="changePage(currentPage + 1)"
              >
                下一页
              </button>
            </div>
          </div>
          <div
            v-if="listLoading"
            class="absolute inset-0 flex items-center justify-center bg-white/55 backdrop-blur-[1px]"
          >
            <span
              class="rounded-full bg-white px-3 py-1.5 text-xs font-medium text-indigo-700 shadow"
              >正在更新列表...</span
            >
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  getTraces,
  getTraceWaterfall,
  getAgentStats,
  getToolStats,
  getLLMStats,
  getSlowTraces,
  type TraceSummary,
  type WaterfallSpan,
  type AgentStats,
  type ToolStats,
  type LLMStats,
  type SlowTraceItem,
} from '../api/trace'
import TraceWaterfall from '../components/trace/TraceWaterfall.vue'
import SpanDetail from '../components/trace/SpanDetail.vue'
import TraceStats from '../components/trace/TraceStats.vue'

const loading = ref(true)
const listLoading = ref(false)
const error = ref<string | null>(null)

const traces = ref<TraceSummary[]>([])
const totalTraces = ref(0)
const pageSize = 20
const offset = ref(0)
const filters = reactive({
  task_type: '',
  task_status: '',
  safety_decision: '',
  error_code: '',
})
const agentStats = ref<AgentStats>({})
const toolStats = ref<ToolStats>({})
const llmStats = ref<LLMStats>({
  call_count: 0,
  avg_latency_ms: 0,
  p50_ms: 0,
  p90_ms: 0,
  avg_prompt_tokens: 0,
  avg_completion_tokens: 0,
  total_prompt_tokens: 0,
  total_completion_tokens: 0,
})
const slowTraces = ref<SlowTraceItem[]>([])

const selectedTraceId = ref<string | null>(null)
const waterfallSpans = ref<WaterfallSpan[]>([])
const waterfallTotalMs = ref(0)
const waterfallFirstTokenMs = ref<number | null>(null)
const spanNavStack = ref<WaterfallSpan[]>([])

const selectedSpan = computed(() =>
  spanNavStack.value.length > 0 ? spanNavStack.value[spanNavStack.value.length - 1] : null,
)
const activeFilterCount = computed(
  () => Object.values(filters).filter((value) => value.trim()).length,
)
const currentPage = computed(() => Math.floor(offset.value / pageSize) + 1)
const totalPages = computed(() => Math.max(1, Math.ceil(totalTraces.value / pageSize)))
const pageStart = computed(() => (totalTraces.value ? offset.value + 1 : 0))
const pageEnd = computed(() => Math.min(offset.value + traces.value.length, totalTraces.value))
const selectClass =
  'h-10 w-full appearance-none rounded-xl border border-slate-200 bg-slate-50 py-2 pl-3 pr-9 text-sm font-medium text-slate-700 shadow-sm transition hover:border-slate-300 focus:border-indigo-500 focus:bg-white focus:outline-none focus:ring-4 focus:ring-indigo-100/70'

function navigateToChild(span: WaterfallSpan) {
  spanNavStack.value.push(span)
}

function selectTopSpan(span: WaterfallSpan) {
  spanNavStack.value = [span]
}

function goBack() {
  if (spanNavStack.value.length > 1) {
    spanNavStack.value.pop()
  }
}

function closeSpanDetail() {
  spanNavStack.value = []
}

function filterParams() {
  return {
    task_type: filters.task_type || undefined,
    task_status: filters.task_status || undefined,
    safety_decision: filters.safety_decision || undefined,
    error_code: filters.error_code || undefined,
  }
}

function errorMessage(value: unknown): string {
  return value instanceof Error ? value.message : '加载失败'
}

async function fetchTraceList() {
  const traceList = await getTraces(pageSize, offset.value, filterParams())
  traces.value = traceList.traces
  totalTraces.value = traceList.total
}

async function loadFilteredList() {
  listLoading.value = true
  error.value = null
  try {
    await fetchTraceList()
  } catch (value: unknown) {
    error.value = errorMessage(value)
  } finally {
    listLoading.value = false
  }
}

async function loadList() {
  loading.value = true
  error.value = null
  try {
    const [traceList, agents, tools, llm, slow] = await Promise.all([
      getTraces(pageSize, offset.value, filterParams()),
      getAgentStats(7),
      getToolStats(7),
      getLLMStats(7),
      getSlowTraces(30000, 10),
    ])
    traces.value = traceList.traces
    totalTraces.value = traceList.total
    agentStats.value = agents || {}
    toolStats.value = tools || {}
    llmStats.value = llm || llmStats.value
    slowTraces.value = slow || []
  } catch (value: unknown) {
    error.value = errorMessage(value)
  } finally {
    loading.value = false
  }
}

async function applyFilters() {
  offset.value = 0
  await loadFilteredList()
}

async function clearFilters() {
  filters.task_type = ''
  filters.task_status = ''
  filters.safety_decision = ''
  filters.error_code = ''
  offset.value = 0
  await loadFilteredList()
}

async function changePage(page: number) {
  const target = Math.min(Math.max(page, 1), totalPages.value)
  offset.value = (target - 1) * pageSize
  await loadFilteredList()
}

async function loadDetail(traceId: string) {
  loading.value = true
  error.value = null
  try {
    const waterfall = await getTraceWaterfall(traceId)
    waterfallSpans.value = waterfall.spans
    waterfallTotalMs.value = waterfall.total_duration_ms
    waterfallFirstTokenMs.value = waterfall.first_token_time_ms
    spanNavStack.value = []
  } catch (value: unknown) {
    error.value = errorMessage(value)
    selectedTraceId.value = null
  } finally {
    loading.value = false
  }
}

function refresh() {
  if (selectedTraceId.value) {
    loadDetail(selectedTraceId.value)
  } else {
    loadList()
  }
}

watch(selectedTraceId, (newId) => {
  if (newId) loadDetail(newId)
})

function modeLabel(mode: string): string {
  const map: Record<string, string> = {
    single_agent: '单Agent',
    swarm: 'Swarm',
    fallback: '降级',
  }
  return map[mode] || mode
}

function modeBadge(mode: string): string {
  const map: Record<string, string> = {
    single_agent: 'bg-blue-50 text-blue-600',
    swarm: 'bg-purple-50 text-purple-600',
    fallback: 'bg-amber-50 text-amber-600',
  }
  return map[mode] || 'bg-slate-50 text-slate-600'
}

function taskTypeLabel(taskType: string): string {
  const labels: Record<string, string> = {
    triage: '症状自测',
    knowledge_search: '知识搜索',
    report_interpretation: '报告解读',
  }
  return labels[taskType] || taskType
}

function taskStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    created: '已创建',
    collecting: '待补充',
    processing: '处理中',
    waiting_confirmation: '待确认',
    completed: '已完成',
    needs_medical_attention: '需就医',
    failed: '失败',
    cancelled: '已取消',
  }
  return labels[status] || status
}

function safetyDecisionLabel(decision: string): string {
  const labels: Record<string, string> = {
    allow: '允许',
    allow_with_notice: '附提示',
    medical_attention: '需就医',
    emergency_stop: '紧急停止',
    manual_review: '人工复核',
  }
  return labels[decision] || decision
}

function safetyDecisionClass(decision: string): string {
  if (decision === 'emergency_stop') return 'bg-red-50 text-red-700'
  if (decision === 'medical_attention' || decision === 'manual_review') {
    return 'bg-amber-50 text-amber-700'
  }
  if (decision === 'allow') return 'bg-emerald-50 text-emerald-700'
  return 'bg-blue-50 text-blue-700'
}

function formatTime(isoStr: string): string {
  if (!isoStr) return '-'
  const d = new Date(isoStr)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const route = useRoute()

onMounted(() => {
  const tid = route.params.traceId as string | undefined
  if (tid) {
    selectedTraceId.value = tid
  } else {
    loadList()
  }
})
</script>
