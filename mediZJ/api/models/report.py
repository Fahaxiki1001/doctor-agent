"""Medical report extraction, confirmation and explanation models."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator

from mediZJ.api.models.task import HealthTaskResponse


class ReportStatus(str, Enum):
    UPLOADED = "uploaded"
    ANALYZING = "analyzing"
    WAITING_CONFIRMATION = "waiting_confirmation"
    PROCESSING = "processing"
    COMPLETED = "completed"
    MANUAL_REVIEW = "manual_review"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReportDocumentType(str, Enum):
    LAB_REPORT = "lab_report"
    PHYSICAL_EXAM = "physical_exam"
    OTHER = "other"


class AbnormalFlag(str, Enum):
    LOW = "low"
    HIGH = "high"
    NORMAL = "normal"
    UNKNOWN = "unknown"


class ReportMeasurement(BaseModel):
    measurement_id: str = ""
    name: str = Field(min_length=1, max_length=200)
    value: Optional[str] = Field(default=None, max_length=100)
    unit: Optional[str] = Field(default=None, max_length=100)
    reference_range: Optional[str] = Field(default=None, max_length=200)
    abnormal_flag: AbnormalFlag = AbnormalFlag.UNKNOWN
    confidence: float = Field(default=0, ge=0, le=1)
    raw_text: Optional[str] = Field(default=None, max_length=1000)
    user_confirmed: bool = False
    unable_to_confirm: bool = False


class ReportAnalysisDraft(BaseModel):
    document_type: ReportDocumentType = ReportDocumentType.OTHER
    measurements: List[ReportMeasurement] = Field(default_factory=list)
    confidence: float = Field(default=0, ge=0, le=1)
    warnings: List[str] = Field(default_factory=list)
    manual_review: bool = False


class MeasurementConfirmation(BaseModel):
    measurement_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=200)
    value: Optional[str] = Field(default=None, max_length=100)
    unit: Optional[str] = Field(default=None, max_length=100)
    reference_range: Optional[str] = Field(default=None, max_length=200)
    user_confirmed: bool = False
    unable_to_confirm: bool = False
    deleted: bool = False

    @model_validator(mode="after")
    def validate_confirmation(self):
        if self.user_confirmed and self.unable_to_confirm:
            raise ValueError("确认与无法确认不能同时选择")
        return self


class ConfirmMeasurementsRequest(BaseModel):
    measurements: List[MeasurementConfirmation] = Field(min_length=1)


class ReportInterpretation(BaseModel):
    confirmed_measurements: List[Dict[str, Any]] = Field(default_factory=list)
    explanations: List[Dict[str, Any]] = Field(default_factory=list)
    medical_attention: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    safety_decision: str


class ReportResponse(BaseModel):
    report_id: str
    task: HealthTaskResponse
    document_type: ReportDocumentType
    status: ReportStatus
    image_url: str
    measurements: List[ReportMeasurement] = Field(default_factory=list)
    result: Optional[ReportInterpretation] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str
