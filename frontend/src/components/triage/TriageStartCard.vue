<script setup lang="ts">
import { ref } from 'vue'

defineProps<{ loading?: boolean }>()
const emit = defineEmits<{ start: [symptom: string] }>()
const symptom = ref('')

function submit() {
  const value = symptom.value.trim()
  if (value) emit('start', value)
}
</script>

<template>
  <section class="border-b border-slate-200 bg-white px-4 py-6 sm:px-6">
    <div class="mx-auto max-w-3xl">
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
          {{ loading ? '评估中...' : '开始自测' }}
        </button>
      </div>
    </div>
  </section>
</template>
