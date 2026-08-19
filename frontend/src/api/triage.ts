import api from './client'
import type { TriageTaskResponse } from '../types'

export async function createTriage(
  symptom: string,
  answers: Record<string, unknown> = {},
): Promise<TriageTaskResponse> {
  const { data } = await api.post('/triage/tasks', { symptom, answers })
  return data
}

export async function getTriage(taskId: string): Promise<TriageTaskResponse> {
  const { data } = await api.get(`/triage/tasks/${taskId}`)
  return data
}

export async function answerTriage(
  taskId: string,
  questionnaireId: string,
  answers: Record<string, unknown>,
): Promise<TriageTaskResponse> {
  const { data } = await api.post(`/triage/tasks/${taskId}/answer`, {
    questionnaire_id: questionnaireId,
    answers,
  })
  return data
}

export async function deleteTriage(taskId: string): Promise<void> {
  await api.delete(`/triage/tasks/${taskId}`)
}
