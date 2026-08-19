"""Privacy-aware Trace lifecycle for consumer health tasks.

Health workflows do not run through :class:`SwarmCoordinator`, but they still
need the same operational observability contract as chat requests.  This
service keeps the trace payload content-light and makes every workflow
operation independently queryable (create, resume, analyze, confirm, etc.).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Optional

from loguru import logger

from mediZJ.api.models.task import HealthTaskResponse, TaskStatus


@dataclass
class HealthTaskTraceHandle:
    trace_id: str
    task_id: str
    task_type: str
    user_id: str
    operation: str
    collector: Any
    root: Any
    stage: Any
    context_token: Any = None
    span_stack_token: Any = None


class HealthTaskTraceService:
    """Create and flush content-light traces for health task operations."""

    def start(
        self,
        task: HealthTaskResponse,
        *,
        user_id: str,
        operation: str,
    ) -> HealthTaskTraceHandle:
        from mediZJ.trace.collector import TraceCollector
        from mediZJ.trace.context import _current_span_stack, _current_trace_id
        from mediZJ.trace.models import Span, SpanType
        from mediZJ.trace.storage import TraceSqliteStorage

        trace_id = str(uuid.uuid4())
        collector = TraceCollector()
        collector.begin_trace(trace_id)
        if not getattr(collector, "_storage_set", False):
            collector.set_storage(TraceSqliteStorage())
            setattr(collector, "_storage_set", True)

        root = collector.get_flat_spans(trace_id)[0]
        stage = Span(
            trace_id=trace_id,
            parent_id=trace_id,
            span_type=SpanType.STAGE,
            name=operation,
        )
        collector.collect(stage)
        token = _current_trace_id.set(trace_id)
        stack_token = _current_span_stack.set([stage])
        return HealthTaskTraceHandle(
            trace_id=trace_id,
            task_id=task.task_id,
            task_type=task.task_type.value,
            user_id=user_id,
            operation=operation,
            collector=collector,
            root=root,
            stage=stage,
            context_token=token,
            span_stack_token=stack_token,
        )

    def finish(
        self,
        handle: Optional[HealthTaskTraceHandle],
        *,
        task: HealthTaskResponse,
        risk_level: str = "",
        safety_decision: str = "",
        error_code: str = "",
        error: Optional[BaseException] = None,
    ) -> None:
        if handle is None:
            return

        from mediZJ.trace.context import _current_span_stack, _current_trace_id
        from mediZJ.trace.models import SpanStatus, TraceAttributes

        if error is not None:
            handle.stage.status = SpanStatus.ERROR
            handle.stage.error_message = type(error).__name__
            handle.root.status = SpanStatus.ERROR
        elif task.status in {TaskStatus.FAILED}:
            handle.stage.status = SpanStatus.ERROR
            handle.root.status = SpanStatus.ERROR
        elif task.status == TaskStatus.CANCELLED:
            handle.stage.status = SpanStatus.TIMEOUT
            handle.root.status = SpanStatus.TIMEOUT

        handle.stage.timing.finish()
        handle.root.timing.finish()
        handle.root.trace_attrs = TraceAttributes(
            # Do not put symptom text, report text, values or image paths into
            # operational traces.  The task id remains the controlled join key.
            session_id=task.session_id or f"health:{task.task_id}",
            user_id=handle.user_id,
            mode="health_task",
            question_summary=f"健康任务:{handle.task_type}",
            task_id=handle.task_id,
            task_type=handle.task_type,
            task_status=task.status.value,
            risk_level=risk_level,
            safety_decision=safety_decision,
            error_code=error_code or (type(error).__name__ if error else ""),
        )
        try:
            handle.collector.flush_sync(handle.trace_id)
        finally:
            try:
                _current_span_stack.reset(handle.span_stack_token)
                _current_trace_id.reset(handle.context_token)
            except (LookupError, ValueError):
                pass

    @staticmethod
    def risk_and_safety(task: HealthTaskResponse) -> tuple[str, str]:
        result = task.result or {}
        risk = str(result.get("risk_level", ""))
        safety = ""
        if task.safety_flags:
            safety = str(task.safety_flags[-1].get("decision", ""))
        return risk, safety


def set_task_trace(task_service: Any, task: HealthTaskResponse, user_id: str, trace_id: str) -> HealthTaskResponse:
    """Persist the latest operation trace id without exposing task content."""

    try:
        return task_service.update(task.task_id, user_id, trace_id=trace_id)
    except Exception as exc:  # observability must never break a health flow
        logger.warning("health task trace id update failed: {}", exc)
        return task
