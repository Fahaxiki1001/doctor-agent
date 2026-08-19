import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import QuestionnaireCard from '../QuestionnaireCard.vue'
import type { QuestionnaireData } from '../../../types'

const questionnaire: QuestionnaireData = {
  questionnaire_id: 'questionnaire-1',
  questions: [
    {
      id: 'severity',
      header: '程度',
      type: 'enum',
      required: true,
      text: '症状有多严重？',
      options: [{ label: '轻微' }, { label: '严重' }],
    },
    {
      id: 'symptoms',
      header: '伴随症状',
      type: 'multi',
      required: true,
      text: '有哪些伴随症状？',
      options: [{ label: '恶心' }, { label: '发热' }],
    },
    {
      id: 'duration',
      header: '持续时间',
      type: 'enum',
      required: true,
      text: '持续了多久？',
      options: [{ label: '一天内' }, { label: '超过一天' }],
    },
  ],
}

describe('QuestionnaireCard', () => {
  it('选择非末题的单选答案后自动进入下一题', async () => {
    const wrapper = mount(QuestionnaireCard, { props: { questionnaire } })

    await wrapper.get('input[type="radio"][value="轻微"]').setValue(true)

    expect(wrapper.text()).toContain('有哪些伴随症状？')
    expect(wrapper.text()).toContain('2 / 3')
  })

  it('多选答案不会自动跳题，用户可以继续选择', async () => {
    const wrapper = mount(QuestionnaireCard, { props: { questionnaire } })
    await wrapper.get('input[type="radio"][value="轻微"]').setValue(true)

    await wrapper.get('input[type="checkbox"][value="恶心"]').setValue(true)

    expect(wrapper.text()).toContain('有哪些伴随症状？')
    expect(wrapper.text()).toContain('2 / 3')
  })

  it('末题单选后保留提交确认并携带所有答案', async () => {
    const wrapper = mount(QuestionnaireCard, { props: { questionnaire } })
    await wrapper.get('input[type="radio"][value="轻微"]').setValue(true)
    await wrapper.get('input[type="checkbox"][value="恶心"]').setValue(true)
    await wrapper.get('.qc-next-btn').trigger('click')

    await wrapper.get('input[type="radio"][value="一天内"]').setValue(true)

    expect(wrapper.text()).toContain('3 / 3')
    expect(wrapper.emitted('submit')).toBeUndefined()

    await wrapper.get('.qc-submit-btn').trigger('click')
    expect(wrapper.emitted('submit')).toEqual([
      [{ severity: '轻微', symptoms: ['恶心'], duration: '一天内' }],
    ])
  })
})
