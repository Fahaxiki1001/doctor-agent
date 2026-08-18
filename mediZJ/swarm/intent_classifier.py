"""意图识别：判断用户输入是否涉及医疗/健康诉求，用于门控长期记忆检索。"""

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, Dict

from mediZJ.core.llm_client import LLMClient
from mediZJ.core.prompt_loader import PromptLoader

# 合法意图取值
_MEDICAL = "medical"
_OTHERS = "others"
_VALID_INTENTS = frozenset({_MEDICAL, _OTHERS})

# 规则快路：命中即判 medical，省掉一次 LLM 往返。
# 只对 medical 方向做快路——把医疗问题误判成闲聊会直接送进 chat_reply，
# 是唯一不可接受的错误方向，所以 others 一律回落 LLM。
_MEDICAL_KEYWORDS = frozenset({
    "疼", "痛", "发烧", "发热", "咳嗽", "咳痰", "头晕", "恶心", "呕吐", "腹泻",
    "血压", "血糖", "血脂", "心率", "过敏", "皮疹", "失眠", "水肿",
    "用药", "服药", "吃药", "剂量", "副作用", "忌口", "疗程",
    "症状", "病史", "检查", "化验", "复查", "就医", "挂号", "门诊", "手术",
    "医生", "医院", "科室", "确诊", "治疗", "康复",
})

# 规则结果的置信度：刻意低于 clarify 短路门限（0.95），
# 避免用置信度数值隐式控制"是否跳过澄清"。
_RULE_CONFIDENCE = 0.9


@dataclass
class IntentResult:
    """意图识别结果。"""

    intent: str            # medical | others
    confidence: float      # 0.0 ~ 1.0
    source: str            # "rule" | "llm" | "fallback"
    reason: str = ""

    @property
    def skip_long_term(self) -> bool:
        """是否跳过 Mem0 长期记忆检索（仅非医疗输入跳过）。"""
        return self.intent == _OTHERS


def try_rule_classify(question: str) -> IntentResult | None:
    """医疗关键词规则快路：命中即判 medical，不调用 LLM。

    只做 medical 方向的判定。判 others 的错误代价（医疗问题被送进闲聊直答）
    远高于多调一次 LLM，因此未命中一律返回 None 回落 LLM。
    """
    text = (question or "").strip()
    if not text:
        return None
    hit = next((w for w in _MEDICAL_KEYWORDS if w in text), None)
    if hit is None:
        return None
    return IntentResult(
        intent=_MEDICAL,
        confidence=_RULE_CONFIDENCE,
        source="rule",
        reason=f"命中医疗关键词: {hit}",
    )


class IntentClassifier:
    """意图识别器：医疗关键词规则快路 + LLM 兜底判断。

    医学安全优先：判断失败或不确定时一律降级为 medical（不跳过检索），
    宁可多检索一次 Mem0，也不丢医疗问题。
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        timeout: float | None = None,
    ) -> None:
        self.llm_client = llm_client or LLMClient()
        self.timeout = (
            timeout
            if timeout is not None
            else float(os.getenv("INTENT_CLASSIFIER_TIMEOUT", "15"))
        )

    async def classify(self, question: str) -> IntentResult:
        """对用户输入进行意图识别。

        Args:
            question: 用户原始输入。

        Returns:
            IntentResult：intent 为 medical 或 others。
            命中医疗关键词时走规则快路（source="rule"），不调用 LLM。
            任何异常（超时、JSON 解析失败、网络错误）均降级为 medical。
        """
        rule_result = try_rule_classify(question)
        if rule_result is not None:
            return rule_result

        try:
            prompt = PromptLoader.render("memory/intent_gate.j2", question=question)
            raw = await asyncio.wait_for(
                self.llm_client.chat(
                    [
                        {
                            "role": "system",
                            "content": "你是医疗助手的意图识别模块，仅输出 JSON。",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0,
                    response_format={"type": "json_object"},
                ),
                timeout=self.timeout,
            )
            return self._normalize(json.loads(raw))
        except (asyncio.TimeoutError, json.JSONDecodeError, KeyError) as exc:
            return self._fallback(reason=f"意图识别失败: {exc}")
        except Exception as exc:
            return self._fallback(reason=f"意图识别异常: {exc}")

    @staticmethod
    def _normalize(raw: Dict[str, Any]) -> IntentResult:
        """校验并归一化 LLM 输出；未知意图/缺字段时保守兜底为 medical。"""
        intent = str(raw.get("intent", ""))
        if intent not in _VALID_INTENTS:
            return IntentResult(
                intent=_MEDICAL,
                confidence=0.0,
                source="fallback",
                reason=f"未知意图值: {intent!r}",
            )
        try:
            confidence = max(0.0, min(1.0, float(raw.get("confidence", 0.0))))
        except (TypeError, ValueError):
            confidence = 0.0
        return IntentResult(
            intent=intent,
            confidence=confidence,
            source="llm",
            reason=str(raw.get("reason", "")).strip(),
        )

    @staticmethod
    def _fallback(reason: str) -> IntentResult:
        return IntentResult(
            intent=_MEDICAL,
            confidence=0.0,
            source="fallback",
            reason=reason,
        )
