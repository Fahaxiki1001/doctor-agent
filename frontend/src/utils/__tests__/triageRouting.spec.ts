import { describe, expect, it } from 'vitest'
import { shouldSuggestTriage } from '../triageRouting'

describe('shouldSuggestTriage', () => {
  it.each(['我从昨天开始发烧并咳嗽', '胸痛要不要去医院', '孩子突然呕吐怎么办'])(
    '对正在发生的症状提示分诊：%s',
    (question) => {
      expect(shouldSuggestTriage(question)).toBe(true)
    },
  )

  it.each(['高血压患者饮食注意事项', '布洛芬有哪些注意事项', '如何改善睡眠质量'])(
    '普通健康知识咨询不提示分诊：%s',
    (question) => {
      expect(shouldSuggestTriage(question)).toBe(false)
    },
  )
})
