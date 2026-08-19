import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('../../api/triage', () => ({
  createTriage: vi.fn(),
  getTriage: vi.fn(),
  answerTriage: vi.fn(),
  deleteTriage: vi.fn(),
}))

import * as triageApi from '../../api/triage'
import { useTriageStore } from '../triage'
import type { TriageTaskResponse } from '../../types'

const collecting: TriageTaskResponse = {
  task: {
    task_id: 'triage-1',
    task_type: 'triage',
    status: 'collecting',
    input_snapshot: { symptom: '头痛' },
    result: {},
    safety_flags: [],
    created_at: '2026-01-01T00:00:00',
    updated_at: '2026-01-01T00:00:00',
  },
  questionnaire: {
    questionnaire_id: 'q1',
    questions: [{ id: 'duration', text: '多久', type: 'input', required: true, options: [] }],
  },
}

describe('triage store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('创建后保存任务并可刷新恢复', async () => {
    vi.mocked(triageApi.createTriage).mockResolvedValue(collecting)
    vi.mocked(triageApi.getTriage).mockResolvedValue(collecting)
    const store = useTriageStore()

    await store.start('头痛')
    expect(localStorage.getItem('medizj_active_triage')).toBe('triage-1')

    store.current = null
    await store.restore()
    expect(store.current).toEqual(collecting)
  })
})
