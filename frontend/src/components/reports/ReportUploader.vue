<script setup lang="ts">
import { ref } from 'vue'

defineProps<{ loading?: boolean }>()
const emit = defineEmits<{
  upload: [file: File, type: 'lab_report' | 'physical_exam' | 'other']
}>()
const file = ref<File | null>(null)
const type = ref<'lab_report' | 'physical_exam' | 'other'>('lab_report')
const input = ref<HTMLInputElement | null>(null)

function selected(event: Event) {
  file.value = (event.target as HTMLInputElement).files?.[0] || null
}

const reportTypes = [
  { value: 'lab_report', label: '检验报告', hint: '血液、尿液等化验单' },
  { value: 'physical_exam', label: '体检报告', hint: '体检中心综合报告' },
  { value: 'other', label: '其他报告', hint: '其他可识别医学报告' },
] as const
</script>

<template>
  <section class="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
    <div class="grid gap-6 p-5 sm:grid-cols-[1fr_260px] sm:p-6">
      <div>
        <div class="flex items-start gap-3">
          <span
            class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600"
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
                d="M9 12h6m-3-3v6m7 4V5a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2Z"
              />
            </svg>
          </span>
          <div>
            <h2 class="text-base font-semibold text-slate-900">上传检查报告</h2>
            <p class="mt-1 text-sm text-slate-500">支持 JPEG、PNG、GIF、WebP，单张不超过 10MB</p>
          </div>
        </div>
        <button
          type="button"
          class="group mt-5 flex min-h-32 w-full flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 text-center transition hover:border-blue-400 hover:bg-blue-50"
          @click="input?.click()"
        >
          <svg
            class="mb-2 h-7 w-7 text-slate-400 transition group-hover:text-blue-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="1.8"
              d="M4 16.5V19a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2.5M12 3v13m0-13L7.5 7.5M12 3l4.5 4.5"
            />
          </svg>
          <span class="text-sm font-medium text-slate-700 group-hover:text-blue-700">{{
            file?.name || '点击选择报告图片'
          }}</span>
          <span v-if="!file" class="mt-1 text-xs text-slate-400"
            >请先遮挡姓名、证件号等个人信息</span
          >
        </button>
        <input
          ref="input"
          class="hidden"
          type="file"
          accept="image/jpeg,image/png,image/gif,image/webp"
          @change="selected"
        />
      </div>
      <div class="flex flex-col justify-between gap-4">
        <fieldset>
          <legend class="mb-2 text-sm font-semibold text-slate-800">选择报告类型</legend>
          <div
            class="grid grid-cols-3 gap-2 sm:grid-cols-1"
            role="radiogroup"
            aria-label="报告类型"
          >
            <label
              v-for="item in reportTypes"
              :key="item.value"
              class="cursor-pointer rounded-xl border px-3 py-2.5 transition"
              :class="
                type === item.value
                  ? 'border-blue-500 bg-blue-50 shadow-sm ring-1 ring-blue-500'
                  : 'border-slate-200 bg-white hover:border-blue-300 hover:bg-slate-50'
              "
            >
              <input v-model="type" class="sr-only" type="radio" :value="item.value" />
              <span
                class="block text-sm font-semibold"
                :class="type === item.value ? 'text-blue-800' : 'text-slate-700'"
                >{{ item.label }}</span
              >
              <span class="mt-0.5 hidden text-xs leading-5 text-slate-500 sm:block">{{
                item.hint
              }}</span>
            </label>
          </div>
        </fieldset>
        <button
          type="button"
          :disabled="loading || !file"
          class="h-11 rounded-xl bg-blue-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 hover:shadow disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none"
          @click="file && emit('upload', file, type)"
        >
          {{ loading ? '识别中...' : '上传并识别' }}
        </button>
      </div>
    </div>
  </section>
</template>
