import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { KnowledgeCenterItem, KnowledgeDocumentPreview } from '../types'
import {
  continueKnowledgeChat,
  getKnowledgeCategories,
  getKnowledgePreview,
  searchKnowledge,
} from '../api/knowledge'
import { getHealthTask } from '../api/tasks'

export const useKnowledgeCenterStore = defineStore('knowledge-center', () => {
  const query = ref('')
  const category = ref('')
  const results = ref<KnowledgeCenterItem[]>([])
  const categories = ref<Array<{ key: string; label: string; description: string }>>([])
  const searchId = ref('')
  const preview = ref<KnowledgeDocumentPreview | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  function messageFrom(errorValue: unknown) {
    return (
      (errorValue as { response?: { data?: { detail?: string } } }).response?.data?.detail ||
      (errorValue instanceof Error ? errorValue.message : '知识检索失败')
    )
  }

  async function loadCategories() {
    try {
      categories.value = await getKnowledgeCategories()
    } catch (err) {
      error.value = messageFrom(err)
    }
  }

  async function search() {
    if (!query.value.trim()) return
    loading.value = true
    error.value = null
    preview.value = null
    try {
      const data = await searchKnowledge({
        query: query.value.trim(),
        filter_type: category.value || undefined,
        top_k: 8,
      })
      results.value = data.results || []
      searchId.value = data.search_id
    } catch (err) {
      results.value = []
      error.value = messageFrom(err)
    } finally {
      loading.value = false
    }
  }

  async function openPreview(docId: string) {
    loading.value = true
    error.value = null
    try {
      preview.value = await getKnowledgePreview(docId)
    } catch (err) {
      error.value = messageFrom(err)
    } finally {
      loading.value = false
    }
  }

  async function continueChat(docId: string) {
    if (!searchId.value) return null
    return continueKnowledgeChat(searchId.value, [docId])
  }

  async function restore(taskId: string) {
    loading.value = true
    error.value = null
    try {
      const task = await getHealthTask(taskId)
      if (task.task_type !== 'knowledge_search') throw new Error('知识搜索记录不存在')
      query.value = String(task.result.query || task.input_snapshot.query || '')
      category.value = String(task.result.category || task.input_snapshot.category || '')
      searchId.value = task.task_id
      const sources = Array.isArray(task.result.sources) ? task.result.sources : []
      results.value = sources.map((source) => {
        const item = source as Record<string, unknown>
        return {
          id: String(item.doc_id || ''),
          content: String(item.snippet || ''),
          score: Number(item.score || 0),
          metadata: {
            doc_id: String(item.doc_id || ''),
            source: String(item.source || ''),
            filename: String(item.title || ''),
            type: String(item.type || ''),
            published_at: item.published_at,
            reviewed_at: item.reviewed_at,
            applicable_population: item.applicable_population,
          },
        }
      })
    } catch (err) {
      results.value = []
      error.value = messageFrom(err)
    } finally {
      loading.value = false
    }
  }

  return {
    query,
    category,
    results,
    categories,
    searchId,
    preview,
    loading,
    error,
    loadCategories,
    search,
    openPreview,
    continueChat,
    restore,
  }
})
