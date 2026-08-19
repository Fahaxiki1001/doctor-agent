<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import ReportUploader from '../components/reports/ReportUploader.vue'
import { useReportStore } from '../stores/report'

const store = useReportStore()
const router = useRouter()

const statusLabel: Record<string, string> = {
  uploaded: '待识别',
  analyzing: '识别中',
  waiting_confirmation: '待确认',
  manual_review: '需人工核对',
  processing: '生成解释中',
  completed: '已完成',
  failed: '识别失败',
  cancelled: '已取消',
}

const statusClass: Record<string, string> = {
  uploaded: 'bg-slate-100 text-slate-600',
  analyzing: 'bg-blue-50 text-blue-700',
  waiting_confirmation: 'bg-amber-50 text-amber-700',
  manual_review: 'bg-amber-50 text-amber-700',
  processing: 'bg-blue-50 text-blue-700',
  completed: 'bg-emerald-50 text-emerald-700',
  failed: 'bg-red-50 text-red-700',
  cancelled: 'bg-slate-100 text-slate-500',
}

function reportTypeLabel(type: string) {
  if (type === 'lab_report') return '检验报告'
  if (type === 'physical_exam') return '体检报告'
  return '医学报告'
}

async function upload(file: File, type: 'lab_report' | 'physical_exam' | 'other') {
  const report = await store.upload(file, type)
  if (report) await router.push(`/reports/${report.report_id}`)
}

onMounted(store.loadList)
</script>

<template>
  <div class="h-full overflow-y-auto bg-slate-50 px-4 py-6 pb-24 sm:px-6 lg:pb-6">
    <div class="mx-auto max-w-5xl space-y-7">
      <ReportUploader :loading="store.loading" @upload="upload" />
      <div
        v-if="store.error"
        role="alert"
        class="border border-red-200 bg-red-50 p-3 text-sm text-red-800"
      >
        {{ store.error }}
      </div>
      <section>
        <div class="flex items-end justify-between gap-3">
          <div>
            <h2 class="text-base font-semibold text-slate-900">历史报告</h2>
            <p class="mt-1 text-xs text-slate-500">仅展示当前账号上传的报告</p>
          </div>
          <span v-if="store.reports.length" class="text-xs text-slate-400">
            共 {{ store.reports.length }} 份
          </span>
        </div>
        <div
          v-if="store.loading && !store.reports.length"
          class="mt-3 rounded-2xl border border-slate-200 bg-white py-12 text-center text-sm text-slate-500"
        >
          加载中...
        </div>
        <div
          v-else-if="!store.reports.length"
          class="mt-3 rounded-2xl border border-dashed border-slate-300 bg-white py-12 text-center text-sm text-slate-500"
        >
          暂无报告记录
        </div>
        <div v-else class="mt-3 grid gap-3 sm:grid-cols-2">
          <button
            v-for="report in store.reports"
            :key="report.report_id"
            class="group flex w-full items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-blue-200 hover:shadow-md"
            @click="router.push(`/reports/${report.report_id}`)"
          >
            <span class="flex min-w-0 items-center gap-3">
              <span
                class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-500 transition group-hover:bg-blue-50 group-hover:text-blue-600"
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
                    d="M7 3h7l4 4v14H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Zm7 0v5h5M9 13h6m-6 4h4"
                  />
                </svg>
              </span>
              <span class="min-w-0">
                <span class="block truncate text-sm font-semibold text-slate-900">{{
                  reportTypeLabel(report.document_type)
                }}</span>
                <span class="mt-1 block text-xs text-slate-500">{{
                  new Date(report.created_at).toLocaleString('zh-CN')
                }}</span>
              </span>
            </span>
            <span
              class="shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold"
              :class="statusClass[report.status] || 'bg-slate-100 text-slate-600'"
            >
              {{ statusLabel[report.status] || '状态未知' }}
            </span>
          </button>
        </div>
      </section>
    </div>
  </div>
</template>
