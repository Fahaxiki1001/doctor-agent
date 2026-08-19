"""Unified health-task domain models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    TRIAGE = "triage"
    KNOWLEDGE_SEARCH = "knowledge_search"
    REPORT_INTERPRETATION = "report_interpretation"


class TaskStatus(str, Enum):
    CREATED = "created"
    COLLECTING = "collecting"
    PROCESSING = "processing"
    WAITING_CONFIRMATION = "waiting_confirmation"
    COMPLETED = "completed"
    NEEDS_MEDICAL_ATTENTION = "needs_medical_attention"
    FAILED = "failed"
    CANCELLED = "cancelled"


ALLOWED_TASK_TRANSITIONS: Dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.CREATED: {
        TaskStatus.COLLECTING,
        TaskStatus.PROCESSING,
        TaskStatus.NEEDS_MEDICAL_ATTENTION,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.COLLECTING: {
        TaskStatus.PROCESSING,
        TaskStatus.WAITING_CONFIRMATION,
        TaskStatus.NEEDS_MEDICAL_ATTENTION,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.PROCESSING: {
        TaskStatus.WAITING_CONFIRMATION,
        TaskStatus.COMPLETED,
        TaskStatus.NEEDS_MEDICAL_ATTENTION,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.WAITING_CONFIRMATION: {
        TaskStatus.PROCESSING,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.FAILED: {TaskStatus.PROCESSING, TaskStatus.CANCELLED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.NEEDS_MEDICAL_ATTENTION: set(),
    TaskStatus.CANCELLED: set(),
}


class InvalidTaskTransition(ValueError):
    """Raised when a task lifecycle transition is not allowed."""


def ensure_task_transition(current: TaskStatus, target: TaskStatus) -> None:
    """Validate a lifecycle transition, allowing idempotent updates."""

    if current == target:
        return
    if target not in ALLOWED_TASK_TRANSITIONS[current]:
        raise InvalidTaskTransition(
            f"任务状态不能从 {current.value} 转换为 {target.value}"
        )


class HealthTaskCreate(BaseModel):
    task_type: TaskType
    session_id: Optional[str] = Field(default=None, max_length=128)
    input_snapshot: Dict[str, Any] = Field(default_factory=dict)
    expires_at: Optional[datetime] = None


class HealthTaskResponse(BaseModel):
    task_id: str
    task_type: TaskType
    session_id: Optional[str] = None
    status: TaskStatus
    input_snapshot: Dict[str, Any] = Field(default_factory=dict)
    result: Dict[str, Any] = Field(default_factory=dict)
    safety_flags: List[Dict[str, Any]] = Field(default_factory=list)
    trace_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class HealthTaskListResponse(BaseModel):
    tasks: List[HealthTaskResponse] = Field(default_factory=list)
    total: int = 0
    limit: int
    offset: int


class TaskDeleteResponse(BaseModel):
    deleted: bool


class TaskFeedbackRequest(BaseModel):
    rating: str = Field(pattern=r"^(like|dislike)$")
    reason_codes: List[str] = Field(default_factory=list, max_length=10)
    comment: str = Field(default="", max_length=500)


class TaskFeedbackResponse(TaskFeedbackRequest):
    task_id: str
    created_at: datetime
    updated_at: datetime
