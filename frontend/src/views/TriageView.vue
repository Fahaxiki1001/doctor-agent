<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import QuestionnaireCard from '../components/chat/QuestionnaireCard.vue'
import EmergencyNotice from '../components/triage/EmergencyNotice.vue'
import RiskResultCard from '../components/triage/RiskResultCard.vue'
import TriageStartCard from '../components/triage/TriageStartCard.vue'
import { useTriageStore } from '../stores/triage'
import type { QuestionnaireData } from '../types'

const store = useTriageStore()
const route = useRoute()
const router = useRouter()

const questionnaire = computed<QuestionnaireData | null>(() => {
  const value = store.current?.questionnaire
  if (!value) return null
  return {
    questionnaire_id: value.questionnaire_id,
    questions: value.questions.map((question, index) => ({
      id: question.id,
      header: `第 ${index + 1} 项`,
      text: question.text,
      type: question.type,
      required: question.required,
      options: (question.options || []).map((label) => ({ label })),
    })),
  }
})

async function start(symptom: string) {
  await store.start(symptom)
  if (store.current) await router.replace(`/triage/${store.current.task.task_id}`)
}

async function restart() {
  store.reset()
  await router.replace('/triage')
}

onMounted(() => store.restore(route.params.taskId as string | undefined))
</script>

<template>
  <div class="h-full overflow-y-auto bg-slate-50 pb-20 lg:pb-0">
    <TriageStartCard v-if="!store.current" :loading="store.loading" @start="start" />
    <div
      v-if="store.error"
      role="alert"
      class="mx-auto mt-4 max-w-3xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
    >
      {{ store.error }}
    </div>
    <div v-if="store.current" class="mx-auto max-w-3xl px-4 py-6 sm:px-6">
      <div class="mb-4 flex items-center justify-between gap-3">
        <p class="text-sm text-slate-500">
          自测记录 {{ new Date(store.current.task.created_at).toLocaleString('zh-CN') }}
        </p>
        <div class="flex items-center gap-4">
          <button
            v-if="store.current.task.status === 'collecting'"
            class="text-sm font-medium text-red-700 hover:text-red-900"
            @click="store.cancel"
          >
            放弃自测
          </button>
          <button class="text-sm font-medium text-blue-700 hover:text-blue-900" @click="restart">
            重新自测
          </button>
        </div>
      </div>
      <EmergencyNotice
        v-if="store.current.result?.risk_level === 'emergency'"
        :result="store.current.result"
      />
      <RiskResultCard v-else-if="store.current.result" :result="store.current.result" />
      <QuestionnaireCard
        v-else-if="questionnaire"
        :questionnaire="questionnaire"
        :error="store.error || undefined"
        @submit="store.submitAnswers"
      />
      <div v-else class="py-16 text-center text-sm text-slate-500">
        {{ store.loading ? '正在评估...' : '正在恢复任务...' }}
      </div>
    </div>
  </div>
</template>
