import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import RiskResultCard from '../RiskResultCard.vue'
import type { RiskAssessment } from '../../../types'

const result: RiskAssessment = {
  risk_level: 'medium',
  urgency: '建议 24 小时内咨询医生',
  confidence: 0.86,
  key_findings: ['症状持续超过一天'],
  red_flags_checked: [],
  red_flags_found: [],
  next_steps: ['记录体温变化'],
  limitations: ['线上评估不能替代面诊'],
  citations: [],
}

describe('RiskResultCard', () => {
  it('强调紧急度而非诊断置信度，并可继续健康咨询', async () => {
    const wrapper = mount(RiskResultCard, { props: { result } })

    expect(wrapper.text()).toContain('仅用于判断就医紧急度')
    expect(wrapper.text()).not.toContain('评估置信度')

    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('continueConsultation')).toHaveLength(1)
  })
})
