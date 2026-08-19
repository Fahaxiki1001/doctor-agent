import api from './client'
import type { HealthTask, HealthTaskStatus, HealthTaskType } from '../types'

export async function getHealthTasks(params?: {
  task_type?: HealthTaskType
  status?: HealthTaskStatus
  limit?: number
  offset?: number
}): Promise<{ tasks: HealthTask[]; total: number }> {
  const { data } = await api.get('/tasks', { params })
  return data
}

export async function getHealthTask(taskId: string): Promise<HealthTask> {
  const { data } = await api.get(`/tasks/${taskId}`)
  return data
}

export async function cancelHealthTask(taskId: string): Promise<HealthTask> {
  const { data } = await api.post(`/tasks/${taskId}/cancel`)
  return data
}

export async function deleteHealthTask(taskId: string): Promise<void> {
  await api.delete(`/tasks/${taskId}`)
}

export async function submitHealthTaskFeedback(
  taskId: string,
  rating: 'like' | 'dislike',
): Promise<void> {
  await api.post(`/tasks/${taskId}/feedback`, { rating, reason_codes: [], comment: '' })
}
