"""Compatibility parsing for free-form risk and symptom Skill output."""

import json
from typing import Any, List, Optional

from pydantic import BaseModel, Field, ValidationError

from mediZJ.api.models.triage import RiskAssessment, RiskLevel


class SymptomPatternAnalysis(BaseModel):
    """Safe subset of analyze-symptoms output exposed to triage."""

    patterns: List[str] = Field(default_factory=list, max_length=10)


def parse_symptom_analysis(value: Any) -> Optional[SymptomPatternAnalysis]:
    """Validate symptom patterns while deliberately discarding disease guesses."""

    try:
        if isinstance(value, str):
            value = json.loads(value)
        return SymptomPatternAnalysis.model_validate(value)
    except (TypeError, ValueError, json.JSONDecodeError, ValidationError):
        return None


def parse_risk_assessment(value: Any) -> RiskAssessment:
    """Parse structured Skill output and conservatively handle invalid output."""

    try:
        if isinstance(value, str):
            value = json.loads(value)
        if isinstance(value, dict) and "risk_level" in value:
            # Existing assess-risk Skill uses a compact compatibility payload.
            # Normalize it before applying the strict public response schema.
            recommendation = str(
                value.get("recommendation")
                or value.get("urgency")
                or "请根据症状变化及时咨询医务人员"
            )
            value = {
                "risk_level": value["risk_level"],
                "urgency": recommendation,
                "confidence": value.get("confidence", 0.75),
                "key_findings": value.get("key_findings", []),
                "red_flags_checked": value.get("red_flags_checked", []),
                "red_flags_found": value.get("red_flags_found", []),
                "next_steps": value.get("next_steps") or [recommendation],
                "limitations": value.get("limitations")
                or ["Skill 风险评估仅用于风险分层，不能作为疾病诊断"],
                "citations": value.get("citations", []),
            }
        return RiskAssessment.model_validate(value)
    except (TypeError, ValueError, json.JSONDecodeError, ValidationError):
        return RiskAssessment(
            risk_level=RiskLevel.HIGH,
            urgency="信息解析失败，建议尽快由医务人员评估",
            confidence=0,
            key_findings=["自动风险评估结果不完整"],
            next_steps=["如症状明显或持续加重，请尽快就医"],
            limitations=["本次自动评估无法可靠解析，已采用保守风险等级"],
        )
