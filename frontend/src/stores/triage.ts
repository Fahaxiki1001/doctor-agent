import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { TriageTaskResponse } from '../types'
import { answerTriage, createTriage, deleteTriage, getTriage } from '../api/triage'
import { cancelHealthTask } from '../api/tasks'

const STORAGE_KEY = 'medizj_active_triage'

export const useTriageStore = defineStore('triage', () => {
  const current = ref<TriageTaskResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  function messageFrom(errorValue: unknown) {
    const detail = (errorValue as { response?: { data?: { detail?: string } } }).response?.data
      ?.detail
    return detail || (errorValue instanceof Error ? errorValue.message : '操作失败，请重试')
  }

  async function start(symptom: string) {
    loading.value = true
    error.value = null
    try {
      current.value = await createTriage(symptom)
      localStorage.setItem(STORAGE_KEY, current.value.task.task_id)
    } catch (err) {
      error.value = messageFrom(err)
    } finally {
      loading.value = false
    }
  }

  async function restore(taskId?: string) {
    const id = taskId || localStorage.getItem(STORAGE_KEY)
    if (!id) return
    loading.value = true
    error.value = null
    try {
      current.value = await getTriage(id)
      localStorage.setItem(STORAGE_KEY, id)
    } catch (err) {
      error.value = messageFrom(err)
      if (!taskId) localStorage.removeItem(STORAGE_KEY)
    } finally {
      loading.value = false
    }
  }

  async function submitAnswers(answers: Record<string, unknown>) {
    const questionnaire = current.value?.questionnaire
    const taskId = current.value?.task.task_id
    if (!questionnaire || !taskId) return
    loading.value = true
    error.value = null
    try {
      current.value = await answerTriage(taskId, questionnaire.questionnaire_id, answers)
    } catch (err) {
      error.value = messageFrom(err)
    } finally {
      loading.value = false
    }
  }

  async function remove() {
    if (current.value) await deleteTriage(current.value.task.task_id)
    reset()
  }

  async function cancel() {
    if (!current.value) return
    loading.value = true
    error.value = null
    try {
      await cancelHealthTask(current.value.task.task_id)
      reset()
    } catch (err) {
      error.value = messageFrom(err)
    } finally {
      loading.value = false
    }
  }

  function reset() {
    current.value = null
    error.value = null
    localStorage.removeItem(STORAGE_KEY)
  }

  return { current, loading, error, start, restore, submitAnswers, remove, cancel, reset }
})
