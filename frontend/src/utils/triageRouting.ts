const SYMPTOM_PATTERN =
  /发热|发烧|头痛|头疼|胸痛|胸闷|呼吸困难|气短|腹痛|肚子痛|呕吐|恶心|腹泻|咳嗽|咯血|便血|黑便|昏厥|晕厥|眩晕|头晕|心悸|抽搐|皮疹|水肿|麻木|乏力|疼痛|不舒服|不适/

const CURRENT_SYMPTOM_PATTERN =
  /我|本人|孩子|宝宝|老人|家人|现在|今天|昨天|刚刚|最近|这几天|开始|已经|持续|伴有|突然|感觉|出现/

const CARE_SEEKING_PATTERN = /怎么办|怎么回事|严重吗|要不要.*(?:医院|就医)|吃什么药|如何缓解/

/**
 * 对可能正在发生的症状做高召回提示，不拦截健康咨询，也不在前端判断风险等级。
 */
export function shouldSuggestTriage(question: string): boolean {
  const normalized = question.replace(/\s+/g, '')
  if (!normalized || !SYMPTOM_PATTERN.test(normalized)) return false
  return CURRENT_SYMPTOM_PATTERN.test(normalized) || CARE_SEEKING_PATTERN.test(normalized)
}
