import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('../../api/knowledge', () => ({
  continueKnowledgeChat: vi.fn(),
  getKnowledgeCategories: vi.fn(),
  getKnowledgePreview: vi.fn(),
  searchKnowledge: vi.fn(),
}))

vi.mock('../../api/tasks', () => ({
  getHealthTask: vi.fn(),
}))

import { getHealthTask } from '../../api/tasks'
import { useKnowledgeCenterStore } from '../knowledgeCenter'

describe('knowledge center store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('restores a persisted knowledge search without copying full documents', async () => {
    vi.mocked(getHealthTask).mockResolvedValue({
      task_id: 'knowledge-1',
      task_type: 'knowledge_search',
      status: 'completed',
      input_snapshot: { query: '血压' },
      result: {
        query: '血压',
        category: 'clinical_guideline',
        sources: [
          {
            doc_id: 'doc-1',
            title: '高血压指南',
            source: '指南来源',
            snippet: '限盐并定期监测血压。',
            score: 0.91,
          },
        ],
      },
      safety_flags: [],
      created_at: '2026-01-01T00:00:00',
      updated_at: '2026-01-01T00:00:00',
    })
    const store = useKnowledgeCenterStore()

    await store.restore('knowledge-1')

    expect(store.query).toBe('血压')
    expect(store.searchId).toBe('knowledge-1')
    expect(store.results).toHaveLength(1)
    expect(store.results[0].metadata.doc_id).toBe('doc-1')
    expect(store.results[0].content).toBe('限盐并定期监测血压。')
  })
})
