<script setup lang="ts">
import type { ReportInterpretation } from '../../types'

defineProps<{ result: ReportInterpretation }>()
function text(value: unknown) {
  return value == null ? '未提供' : String(value)
}
</script>

<template>
  <section class="space-y-6">
    <div>
      <h2 class="text-base font-semibold text-slate-900">原报告数据</h2>
      <div class="mt-3 overflow-x-auto border border-slate-200 bg-white">
        <table class="w-full min-w-[560px] text-left text-sm">
          <thead class="bg-slate-50 text-slate-600">
            <tr>
              <th class="p-3">项目</th>
              <th class="p-3">数值</th>
              <th class="p-3">单位</th>
              <th class="p-3">参考范围</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-200">
            <tr v-for="item in result.confirmed_measurements" :key="text(item.measurement_id)">
              <td class="p-3 font-medium">{{ text(item.name) }}</td>
              <td class="p-3">{{ text(item.value) }}</td>
              <td class="p-3">{{ text(item.unit) }}</td>
              <td class="p-3">{{ text(item.reference_range) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <div>
      <h2 class="text-base font-semibold text-slate-900">系统解释</h2>
      <div class="mt-3 divide-y divide-slate-200 border-y border-slate-200 bg-white">
        <article v-for="item in result.explanations" :key="text(item.measurement_id)" class="py-4">
          <h3 class="font-medium text-slate-900">{{ text(item.name) }}</h3>
          <p class="mt-1 text-sm leading-6 text-slate-700">{{ text(item.summary) }}</p>
          <p class="mt-1 text-xs text-slate-500">{{ text(item.next_step) }}</p>
        </article>
      </div>
    </div>
    <div v-if="result.medical_attention.length" class="border-l-4 border-red-500 bg-red-50 p-4">
      <h2 class="font-semibold text-red-900">需就医关注</h2>
      <p v-for="item in result.medical_attention" :key="item" class="mt-2 text-sm text-red-900">
        {{ item }}
      </p>
    </div>
    <div class="text-sm text-slate-600">
      <h2 class="font-semibold text-slate-800">能力边界</h2>
      <p v-for="item in result.limitations" :key="item" class="mt-2">{{ item }}</p>
    </div>
  </section>
</template>
