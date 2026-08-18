import { afterEach, describe, expect, it, vi } from 'vitest'

import { typeRemainingText } from '../typewriter'

describe('typeRemainingText', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('在已流式内容后逐步补齐最终答案', () => {
    vi.useFakeTimers()
    const updates: string[] = []
    const onComplete = vi.fn()

    typeRemainingText({
      currentText: '你好',
      targetText: '你好，世界',
      chunkSize: 2,
      intervalMs: 10,
      onUpdate: (text) => updates.push(text),
      onComplete,
    })

    vi.advanceTimersByTime(10)
    expect(updates).toEqual(['你好，世'])
    expect(onComplete).not.toHaveBeenCalled()

    vi.advanceTimersByTime(10)
    expect(updates).toEqual(['你好，世', '你好，世界'])
    expect(onComplete).toHaveBeenCalledOnce()
  })

  it('仅尾部空白不同时只回退空白，不清空重打', () => {
    vi.useFakeTimers()
    const updates: string[] = []
    const onComplete = vi.fn()

    typeRemainingText({
      currentText: '这是正文\n\n',
      targetText: '这是正文',
      chunkSize: 2,
      intervalMs: 10,
      onUpdate: (text) => updates.push(text),
      onComplete,
    })

    expect(updates).toEqual(['这是正文'])
    expect(onComplete).toHaveBeenCalledOnce()

    vi.runAllTimers()
    expect(updates).toEqual(['这是正文'])
  })

  it('内容真实分叉时仍清空后重打', () => {
    vi.useFakeTimers()
    const updates: string[] = []
    const onComplete = vi.fn()

    typeRemainingText({
      currentText: '旧内容',
      targetText: '新答案',
      chunkSize: 3,
      intervalMs: 10,
      onUpdate: (text) => updates.push(text),
      onComplete,
    })

    expect(updates).toEqual([''])

    vi.advanceTimersByTime(10)
    expect(updates).toEqual(['', '新答案'])
    expect(onComplete).toHaveBeenCalledOnce()
  })

  it('已显示内容全为空白时走清空分支', () => {
    vi.useFakeTimers()
    const updates: string[] = []
    const onComplete = vi.fn()

    typeRemainingText({
      currentText: '\n\n',
      targetText: '最终答案',
      chunkSize: 4,
      intervalMs: 10,
      onUpdate: (text) => updates.push(text),
      onComplete,
    })

    expect(updates).toEqual([''])

    vi.advanceTimersByTime(10)
    expect(updates).toEqual(['', '最终答案'])
    expect(onComplete).toHaveBeenCalledOnce()
  })

  it('取消后不再更新内容', () => {
    vi.useFakeTimers()
    const onUpdate = vi.fn()
    const onComplete = vi.fn()
    const controller = typeRemainingText({
      currentText: '',
      targetText: '最终答案',
      onUpdate,
      onComplete,
    })

    controller.cancel()
    vi.runAllTimers()

    expect(onUpdate).not.toHaveBeenCalled()
    expect(onComplete).not.toHaveBeenCalled()
  })
})
