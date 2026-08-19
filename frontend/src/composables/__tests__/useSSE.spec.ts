import { describe, it, expect, vi } from 'vitest'
import { useSSE } from '../useSSE'

/**
 * 模拟 useSSE 的核心流解析逻辑（不涉及 fetch）
 * 验证换行分隔 JSON 解析的正确性
 */
function parseSSEBuffer(buffer: string): Array<{ event: string; data: any }> {
  const results: Array<{ event: string; data: any }> = []
  const lines = buffer.split('\n')
  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) continue
    try {
      const msg = JSON.parse(trimmed)
      results.push({ event: msg.event, data: msg.data })
    } catch {
      /* skip */
    }
  }
  return results
}

describe('useSSE 流解析', () => {
  it('应正确解析单行 JSON', () => {
    const events = parseSSEBuffer('{"event":"start","data":{"session_id":"abc"}}')
    expect(events).toHaveLength(1)
    expect(events[0].event).toBe('start')
    expect(events[0].data.session_id).toBe('abc')
  })

  it('应正确解析多行 JSON', () => {
    const buffer = [
      '{"event":"start","data":{"session_id":"abc"}}',
      '{"event":"agent_content_delta","data":{"token":"你好"}}',
      '{"event":"done","data":{"answer":"你好"}}',
    ].join('\n')
    const events = parseSSEBuffer(buffer)
    expect(events).toHaveLength(3)
    expect(events[0].event).toBe('start')
    expect(events[1].event).toBe('agent_content_delta')
    expect(events[2].event).toBe('done')
  })

  it('应跳过空行', () => {
    const events = parseSSEBuffer('\n\n{"event":"start","data":{}}\n\n')
    expect(events).toHaveLength(1)
  })

  it('应跳过无效 JSON 行', () => {
    const events = parseSSEBuffer('not json\n{"event":"start","data":{}}')
    expect(events).toHaveLength(1)
    expect(events[0].event).toBe('start')
  })

  it('应分发健康任务事件', async () => {
    const encoder = new TextEncoder()
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(
          encoder.encode(
            '{"event":"task_started","data":{"task_id":"t1","task_type":"triage","status":"processing"}}\n' +
              '{"event":"risk_update","data":{"task_id":"t1","task_type":"triage","risk_level":"high"}}\n' +
              '{"event":"task_completed","data":{"task_id":"t1","task_type":"triage","status":"completed"}}\n',
          ),
        )
        controller.close()
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(stream, { status: 200 })))
    const started = vi.fn()
    const risk = vi.fn()
    const completed = vi.fn()

    await useSSE().connect(
      '/api/test',
      {},
      {
        onTaskStarted: started,
        onRiskUpdate: risk,
        onTaskCompleted: completed,
      },
    )

    expect(started).toHaveBeenCalledWith(expect.objectContaining({ task_id: 't1' }))
    expect(risk).toHaveBeenCalledWith(expect.objectContaining({ risk_level: 'high' }))
    expect(completed).toHaveBeenCalledOnce()
    vi.unstubAllGlobals()
  })
})
