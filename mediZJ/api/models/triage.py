"""Structured symptom self-check and triage models."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator

from mediZJ.api.models.task import HealthTaskResponse


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EMERGENCY = "emergency"


class RiskAssessment(BaseModel):
    risk_level: RiskLevel
    urgency: str = Field(min_length=1, max_length=200)
    confidence: float = Field(ge=0, le=1)
    key_findings: List[str] = Field(default_factory=list)
    red_flags_checked: List[str] = Field(default_factory=list)
    red_flags_found: List[str] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_emergency_action(self):
        if self.risk_level == RiskLevel.EMERGENCY and not self.next_steps:
            raise ValueError("紧急风险必须提供行动建议")
        return self


class TriageCreateRequest(BaseModel):
    symptom: str = Field(min_length=1, max_length=2000)
    session_id: Optional[str] = Field(default=None, max_length=128)
    answers: Dict[str, Any] = Field(default_factory=dict)


class TriageAnswerRequest(BaseModel):
    questionnaire_id: str = Field(min_length=1, max_length=128)
    answers: Dict[str, Any] = Field(min_length=1)


class TriageTaskResponse(BaseModel):
    task: HealthTaskResponse
    questionnaire: Optional[Dict[str, Any]] = None
    result: Optional[RiskAssessment] = None
