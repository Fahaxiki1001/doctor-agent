import { describe, expect, it, vi } from 'vitest'
import { createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import ChatMessage from '../ChatMessage.vue'
import type { ChatMessage as ChatMessageType } from '../../../types'

vi.mock('../../../api/evolution', () => ({
  getFeedback: vi.fn().mockResolvedValue(null),
  submitFeedback: vi.fn().mockResolvedValue(undefined),
}))

const Blank = { template: '<div />' }

function buildMessage(): ChatMessageType {
  return {
    role: 'assistant',
    content: '建议多喝水并观察体温变化。',
    isStreaming: false,
    assistantMessageId: 'm1',
    thinkingBlocks: [
      {
        id: 'b1',
        agentId: 'lead_agent',
        iteration: 1,
        phase: 'decompose',
        thinking: '内部分解推理内容',
        toolSteps: [],
        isCollapsed: true,
      },
    ],
    metadata: {
      agentsInvolved: ['consultation_agent'],
      timeToFirstToken: 1.2,
      usage: { total_tokens: 1234 },
    },
  } as unknown as ChatMessageType
}

async function mountAt(path: string) {
  const router = createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/chat', meta: { portal: 'c' }, component: Blank },
      { path: '/o/chat', meta: { portal: 'o' }, component: Blank },
    ],
  })
  await router.push(path)
  await router.isReady()

  return mount(ChatMessage, {
    props: { message: buildMessage() },
    global: { plugins: [createPinia(), router] },
  })
}

describe('ChatMessage 端展示差异', () => {
  it('C 端不展示推理过程与运行指标', async () => {
    const wrapper = await mountAt('/chat')
    const text = wrapper.text()

    expect(text).toContain('建议多喝水并观察体温变化。')
    expect(text).not.toContain('内部分解推理内容')
    expect(text).not.toContain('任务协调')
    expect(text).not.toContain('tokens')
  })

  it('O 端展示推理过程与运行指标', async () => {
    const wrapper = await mountAt('/o/chat')
    const text = wrapper.text()

    expect(text).toContain('任务协调')
    expect(text).toContain('1234')
  })
})
