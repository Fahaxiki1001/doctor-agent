<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{ loading?: boolean; initialSymptom?: string }>()
const emit = defineEmits<{ start: [symptom: string] }>()
const symptom = ref(props.initialSymptom || '')

watch(
  () => props.initialSymptom,
  (value) => {
    if (value && !symptom.value) symptom.value = value
  },
)

function submit() {
  const value = symptom.value.trim()
  if (value) emit('start', value)
}
</script>

<template>
  <section class="border-b border-slate-200 bg-white px-4 py-6 sm:px-6">
    <div class="mx-auto max-w-3xl">
      <div class="mb-6 rounded-2xl border border-blue-100 bg-blue-50/70 p-4 sm:p-5">
        <div class="flex flex-wrap items-center gap-2">
          <h2 class="text-lg font-semibold text-slate-900">判断是否需要尽快就医</h2>
          <span class="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-blue-700">
            通常约 2 分钟
          </span>
        </div>
        <p class="mt-2 text-sm leading-6 text-slate-600">
          根据症状和红旗信号评估就医紧急度，给出下一步行动建议，不提供疾病诊断。
        </p>
      </div>
      <label for="triage-symptom" class="block text-sm font-medium text-slate-800">
        描述当前最主要的不适
      </label>
      <textarea
        id="triage-symptom"
        v-model="symptom"
        rows="4"
        maxlength="2000"
        class="mt-2 w-full resize-none rounded-lg border border-slate-300 bg-white px-3 py-3 text-sm leading-6 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
        placeholder="例如：从昨晚开始发热到 38.5℃，伴有咳嗽，没有呼吸困难"
        @keydown.ctrl.enter="submit"
      />
      <div class="mt-3 flex items-center justify-between gap-3">
        <p class="text-xs text-slate-500">如有危及生命的情况，请直接拨打 120。</p>
        <button
          type="button"
          :disabled="loading || !symptom.trim()"
          class="shrink-0 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
          @click="submit"
        >
          {{ loading ? '评估中...' : '开始症状分诊' }}
        </button>
      </div>
    </div>
  </section>
</template>
