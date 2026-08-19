import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import TriageStartCard from '../TriageStartCard.vue'

describe('TriageStartCard', () => {
  it('展示就医紧急度定位并带入问答中的症状', async () => {
    const wrapper = mount(TriageStartCard, {
      props: { initialSymptom: '从昨晚开始发热到 38.5℃' },
    })

    expect(wrapper.text()).toContain('判断是否需要尽快就医')
    expect(wrapper.text()).toContain('不提供疾病诊断')
    expect(wrapper.get('textarea').element.value).toBe('从昨晚开始发热到 38.5℃')

    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('start')?.[0]).toEqual(['从昨晚开始发热到 38.5℃'])
  })
})
