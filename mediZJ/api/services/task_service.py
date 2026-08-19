"""Application service for unified health tasks."""

import hashlib
import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from mediZJ.api.models.task import (
    HealthTaskCreate,
    HealthTaskListResponse,
    HealthTaskResponse,
    InvalidTaskTransition,
    TaskStatus,
    TaskType,
    ensure_task_transition,
)
from mediZJ.memory.session_db import SessionDB


class TaskNotFoundError(LookupError):
    """An owned task does not exist."""


class TaskService:
    def __init__(self, db: Optional[SessionDB] = None):
        self.db = db or SessionDB()

    @staticmethod
    def _decode_json(value: Any, fallback: Any) -> Any:
        if value in (None, ""):
            return fallback
        if not isinstance(value, str):
            return value
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return fallback

    @classmethod
    def _to_response(cls, row: Dict[str, Any]) -> HealthTaskResponse:
        data = dict(row)
        data["input_snapshot"] = cls._decode_json(data.get("input_snapshot"), {})
        data["result"] = cls._decode_json(data.get("result"), {})
        data["safety_flags"] = cls._decode_json(data.get("safety_flags"), [])
        data.pop("user_id", None)
        return HealthTaskResponse.model_validate(data)

    def create(
        self,
        user_id: str,
        request: HealthTaskCreate,
        *,
        status: TaskStatus = TaskStatus.CREATED,
    ) -> HealthTaskResponse:
        row = self.db.create_health_task(
            {
                "task_id": str(uuid.uuid4()),
                "user_id": user_id,
                "task_type": request.task_type.value,
                "session_id": request.session_id,
                "status": status.value,
                "input_snapshot": request.input_snapshot,
                "expires_at": request.expires_at.isoformat()
                if request.expires_at
                else None,
            }
        )
        return self._to_response(row)

    def get(self, task_id: str, user_id: str) -> HealthTaskResponse:
        row = self.db.get_health_task(task_id, user_id)
        if row is None:
            raise TaskNotFoundError(task_id)
        return self._to_response(row)

    def list(
        self,
        user_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
        task_type: Optional[TaskType] = None,
        status: Optional[TaskStatus] = None,
    ) -> HealthTaskListResponse:
        type_value = task_type.value if task_type else None
        status_value = status.value if status else None
        rows = self.db.list_health_tasks(
            user_id,
            limit=limit,
            offset=offset,
            task_type=type_value,
            status=status_value,
        )
        return HealthTaskListResponse(
            tasks=[self._to_response(row) for row in rows],
            total=self.db.count_health_tasks(user_id, type_value, status_value),
            limit=limit,
            offset=offset,
        )

    def update(
        self,
        task_id: str,
        user_id: str,
        **updates: Any,
    ) -> HealthTaskResponse:
        current = self.get(task_id, user_id)
        target = updates.get("status")
        if target is not None:
            target = TaskStatus(target)
            ensure_task_transition(current.status, target)
            updates["status"] = target.value
        row = self.db.update_health_task(
            task_id,
            user_id,
            updates,
            expected_status=current.status.value if target is not None else None,
        )
        if row is None:
            if self.db.get_health_task(task_id, user_id) is None:
                raise TaskNotFoundError(task_id)
            raise InvalidTaskTransition("任务状态已被其他请求更新，请刷新后重试")
        return self._to_response(row)

    def cancel(self, task_id: str, user_id: str) -> HealthTaskResponse:
        task = self.get(task_id, user_id)
        from mediZJ.api.services.health_task_trace import HealthTaskTraceService, set_task_trace

        trace = HealthTaskTraceService().start(
            task, user_id=user_id, operation="health_task.cancel"
        )
        task = set_task_trace(self, task, user_id, trace.trace_id)
        try:
            cancelled = self.update(task_id, user_id, status=TaskStatus.CANCELLED)
        except Exception as exc:
            HealthTaskTraceService().finish(trace, task=task, error=exc)
            raise
        HealthTaskTraceService().finish(trace, task=cancelled, error_code="cancelled")
        return cancelled

    def delete(self, task_id: str, user_id: str) -> None:
        task = self.get(task_id, user_id)
        if task.task_type == TaskType.REPORT_INTERPRETATION:
            report = self.db.get_report_by_task(task_id)
            if report and report["user_id"] == user_id:
                from mediZJ.api.services.image_upload_service import ImageUploadService

                self.db.delete_report(report["report_id"], user_id)
                ImageUploadService(self.db).delete(
                    report["upload_filename"], user_id
                )
        if not self.db.delete_health_task(task_id, user_id):
            raise TaskNotFoundError(task_id)
        salt = os.getenv("TASK_AUDIT_SALT", "medizj-local-audit")

        def digest(value: str) -> str:
            return hashlib.sha256(f"{salt}:{value}".encode("utf-8")).hexdigest()

        self.db.add_health_task_audit(
            digest(task_id), digest(user_id), task.task_type.value, "deleted"
        )

    def recover_expired(self) -> int:
        """Fail unfinished health tasks whose interaction deadline elapsed."""

        recovered = 0
        from mediZJ.api.services.health_task_trace import HealthTaskTraceService, set_task_trace

        traces = HealthTaskTraceService()
        for row in self.db.list_expired_health_tasks(datetime.now().isoformat()):
            user_id = row["user_id"]
            task = self.get(row["task_id"], user_id)
            trace = traces.start(task, user_id=user_id, operation="health_task.timeout")
            task = set_task_trace(self, task, user_id, trace.trace_id)
            try:
                failed = self.update(
                    task.task_id,
                    user_id,
                    status=TaskStatus.FAILED,
                    safety_flags=[{"decision": "manual_review", "code": "timeout"}],
                )
            except Exception as exc:
                traces.finish(trace, task=task, error=exc, error_code="timeout")
                continue
            traces.finish(trace, task=failed, error_code="timeout")
            recovered += 1
        return recovered
