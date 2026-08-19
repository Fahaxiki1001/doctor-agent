<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MeasurementConfirmTable from '../components/reports/MeasurementConfirmTable.vue'
import ReportResultCard from '../components/reports/ReportResultCard.vue'
import ReportSafetyNotice from '../components/reports/ReportSafetyNotice.vue'
import { useReportStore } from '../stores/report'

const store = useReportStore()
const route = useRoute()
const router = useRouter()

async function remove() {
  if (!store.current || !confirm('确定删除这份报告及其私有图片？')) return
  await store.remove(store.current.report_id)
  await router.replace('/reports')
}

onMounted(() => store.load(route.params.reportId as string))
</script>

<template>
  <div class="h-full overflow-y-auto bg-slate-50 px-4 py-6 pb-24 sm:px-6 lg:pb-6">
    <main class="mx-auto max-w-5xl space-y-6">
      <div class="flex items-center justify-between gap-4">
        <button class="text-sm font-medium text-blue-700" @click="router.push('/reports')">
          返回报告列表
        </button>
        <div v-if="store.current" class="flex items-center gap-4">
          <button
            v-if="
              [
                'uploaded',
                'analyzing',
                'waiting_confirmation',
                'manual_review',
                'processing',
              ].includes(store.current.status)
            "
            class="text-sm font-medium text-amber-700"
            @click="store.cancel"
          >
            取消任务
          </button>
          <button class="text-sm font-medium text-red-700" @click="remove">删除报告</button>
        </div>
      </div>
      <div
        v-if="store.error"
        role="alert"
        class="border border-red-200 bg-red-50 p-3 text-sm text-red-800"
      >
        {{ store.error }}
      </div>
      <div v-if="store.loading && !store.current" class="py-16 text-center text-sm text-slate-500">
        加载中...
      </div>
      <template v-else-if="store.current">
        <ReportSafetyNotice />
        <div
          v-if="store.current.status === 'failed' || store.current.status === 'manual_review'"
          class="border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"
        >
          <p>{{ store.current.error || '识别置信度不足，请核对指标或重试。' }}</p>
          <button
            v-if="store.current.status === 'failed'"
            class="mt-3 font-medium text-blue-700"
            @click="store.retry"
          >
            重新识别
          </button>
        </div>
        <MeasurementConfirmTable
          v-if="
            ['waiting_confirmation', 'manual_review'].includes(store.current.status) &&
            store.current.measurements.length
          "
          :measurements="store.current.measurements"
          :loading="store.loading"
          @confirm="store.confirm"
        />
        <ReportResultCard v-if="store.current.result" :result="store.current.result" />
        <div
          v-if="['uploaded', 'analyzing', 'processing'].includes(store.current.status)"
          class="py-16 text-center text-sm text-slate-500"
        >
          报告处理中...
        </div>
      </template>
    </main>
  </div>
</template>
