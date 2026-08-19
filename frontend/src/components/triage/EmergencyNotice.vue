<script setup lang="ts">
import type { RiskAssessment } from '../../types'

defineProps<{ result: RiskAssessment }>()
</script>

<template>
  <section role="alert" class="border-l-4 border-red-600 bg-red-50 p-5">
    <div class="flex items-start gap-3">
      <svg
        class="mt-0.5 h-6 w-6 shrink-0 text-red-700"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M12 9v4m0 4h.01M10.3 3.8L1.8 18.5A2 2 0 003.5 21h17a2 2 0 001.7-2.5L13.7 3.8a2 2 0 00-3.4 0z"
        />
      </svg>
      <div>
        <h2 class="text-lg font-semibold text-red-900">需要立即获得医疗帮助</h2>
        <p class="mt-1 text-sm font-medium text-red-800">{{ result.urgency }}</p>
        <ol class="mt-4 space-y-2 text-sm text-red-900">
          <li v-for="(step, index) in result.next_steps" :key="step">
            <span class="mr-2 font-semibold">{{ index + 1 }}.</span>{{ step }}
          </li>
        </ol>
      </div>
    </div>
  </section>
</template>
