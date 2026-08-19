"""Conservative safety decisions shared by health tasks."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from mediZJ.constraints.validator import get_shared_validator


class SafetyDecision(str, Enum):
    ALLOW = "allow"
    ALLOW_WITH_NOTICE = "allow_with_notice"
    MEDICAL_ATTENTION = "medical_attention"
    EMERGENCY_STOP = "emergency_stop"
    MANUAL_REVIEW = "manual_review"


class SafetyInput(BaseModel):
    user_text: str = ""
    questionnaire_answers: Dict[str, Any] = Field(default_factory=dict)
    rule_result: Optional[Dict[str, Any] | str] = None
    llm_result: Optional[Dict[str, Any] | str] = None
    vision_confidence: Optional[float] = Field(default=None, ge=0, le=1)
    user_confirmed: Optional[bool] = None
    generated_output: str = ""


class SafetyResult(BaseModel):
    decision: SafetyDecision
    risk_level: str = "low"
    reasons: List[str] = Field(default_factory=list)
    violations: List[str] = Field(default_factory=list)


_RISK_WEIGHT = {"low": 0, "medium": 1, "high": 2, "emergency": 3}
_EMERGENCY_TERMS = (
    "呼吸困难",
    "喘不上气",
    "意识不清",
    "失去意识",
    "大出血",
    "止不住血",
    "严重过敏",
    "喉咙肿",
    "想自杀",
    "自伤",
)


def _risk_from(value: Optional[Dict[str, Any] | str]) -> str:
    if isinstance(value, dict):
        value = value.get("risk_level") or value.get("level") or "low"
    normalized = str(value or "low").lower()
    return normalized if normalized in _RISK_WEIGHT else "low"


class SafetyGate:
    """Merge deterministic, model, confirmation and output constraints."""

    def evaluate(self, payload: SafetyInput) -> SafetyResult:
        rule_risk = _risk_from(payload.rule_result)
        llm_risk = _risk_from(payload.llm_result)
        text_emergency = any(term in payload.user_text for term in _EMERGENCY_TERMS)
        if text_emergency:
            rule_risk = "emergency"
        risk_level = max((rule_risk, llm_risk), key=_RISK_WEIGHT.__getitem__)

        reasons: List[str] = []
        if rule_risk == "emergency":
            reasons.append("确定性高危规则命中")
        elif rule_risk == "high":
            reasons.append("确定性规则提示高风险")
        if _RISK_WEIGHT[llm_risk] > _RISK_WEIGHT[rule_risk]:
            reasons.append("模型评估提示更高风险")

        violations: List[str] = []
        if payload.generated_output:
            checked = get_shared_validator().validate_output(
                "consultation_agent", payload.generated_output
            )
            violations = list(checked.get("violations") or [])

        if rule_risk == "emergency" or risk_level == "emergency":
            decision = SafetyDecision.EMERGENCY_STOP
        elif risk_level == "high":
            decision = SafetyDecision.MEDICAL_ATTENTION
        elif (
            payload.vision_confidence is not None
            and payload.vision_confidence < 0.6
        ) or (
            payload.vision_confidence is not None
            and payload.user_confirmed is not True
        ):
            decision = SafetyDecision.MANUAL_REVIEW
            reasons.append("报告识别置信度不足或尚未由用户确认")
        elif violations or risk_level == "medium":
            decision = SafetyDecision.ALLOW_WITH_NOTICE
            if violations:
                reasons.append("生成内容触发医疗能力边界")
        else:
            decision = SafetyDecision.ALLOW

        return SafetyResult(
            decision=decision,
            risk_level=risk_level,
            reasons=reasons,
            violations=violations,
        )
