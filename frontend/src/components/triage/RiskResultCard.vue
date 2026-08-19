<script setup lang="ts">
import { computed } from 'vue'
import type { RiskAssessment } from '../../types'

const props = defineProps<{ result: RiskAssessment }>()
const emit = defineEmits<{ continueConsultation: [] }>()
const labels = { low: '较低风险', medium: '需关注', high: '较高风险', emergency: '紧急' }
const tone = computed(
  () =>
    ({
      low: 'border-green-500 bg-green-50 text-green-900',
      medium: 'border-amber-500 bg-amber-50 text-amber-950',
      high: 'border-red-500 bg-red-50 text-red-950',
      emergency: 'border-red-700 bg-red-50 text-red-950',
    })[props.result.risk_level],
)
</script>

<template>
  <section class="border-l-4 p-5" :class="tone">
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <h2 class="text-lg font-semibold">{{ labels[result.risk_level] }}</h2>
      <span class="text-xs">仅用于判断就医紧急度</span>
    </div>
    <p class="mt-2 text-sm font-medium">{{ result.urgency }}</p>
    <h3 class="mt-5 text-sm font-semibold">下一步行动</h3>
    <ul class="mt-2 space-y-2 text-sm">
      <li v-for="step in result.next_steps" :key="step" class="flex gap-2">
        <span aria-hidden="true">•</span><span>{{ step }}</span>
      </li>
    </ul>
    <details class="mt-5 text-sm">
      <summary class="cursor-pointer font-medium">查看评估依据与局限</summary>
      <div class="mt-3 space-y-3 text-slate-700">
        <p v-for="finding in result.key_findings" :key="finding">{{ finding }}</p>
        <p v-for="item in result.limitations" :key="item">{{ item }}</p>
      </div>
    </details>
    <div class="mt-5 border-t border-current/15 pt-4">
      <button
        type="button"
        class="rounded-lg bg-white/80 px-4 py-2 text-sm font-semibold shadow-sm ring-1 ring-inset ring-current/20 transition hover:bg-white"
        @click="emit('continueConsultation')"
      >
        继续咨询护理与注意事项 →
      </button>
    </div>
  </section>
</template>
