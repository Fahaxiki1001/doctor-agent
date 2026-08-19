"""Medical report extraction, confirmation and interpretation workflow."""

from __future__ import annotations

import os
import re
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, List, Optional

from fastapi import UploadFile

from mediZJ.api.models.report import (
    AbnormalFlag,
    ConfirmMeasurementsRequest,
    ReportDocumentType,
    ReportInterpretation,
    ReportMeasurement,
    ReportResponse,
    ReportStatus,
)
from mediZJ.api.models.task import HealthTaskCreate, TaskStatus, TaskType
from mediZJ.api.services.image_analyzer import ImageAnalyzer
from mediZJ.api.services.image_upload_service import ImageUploadService
from mediZJ.api.services.knowledge_service import (
    KnowledgeUnavailableError,
    search_knowledge,
)
from mediZJ.api.services.safety_service import SafetyGate, SafetyInput
from mediZJ.api.services.task_service import TaskService
from mediZJ.api.services.health_task_trace import (
    HealthTaskTraceService,
    set_task_trace,
)
from mediZJ.memory.session_db import SessionDB


_NUMBER_PATTERN = re.compile(r"^[<>≤≥]?\s*-?\d+(?:\.\d+)?$")
_RANGE_PATTERN = re.compile(
    r"^\s*(-?\d+(?:\.\d+)?)\s*(?:-|~|至)\s*(-?\d+(?:\.\d+)?)\s*$"
)


class ReportNotFoundError(LookupError):
    pass


class ReportStateError(ValueError):
    pass


class ReportService:
    def __init__(
        self,
        db: Optional[SessionDB] = None,
        task_service: Optional[TaskService] = None,
        upload_service: Optional[ImageUploadService] = None,
        analyzer: Optional[ImageAnalyzer] = None,
        knowledge_search: Callable[..., Any] = search_knowledge,
    ):
        self.db = db or SessionDB()
        self.tasks = task_service or TaskService(self.db)
        self.uploads = upload_service or ImageUploadService(self.db)
        self.analyzer = analyzer or ImageAnalyzer()
        self.knowledge_search = knowledge_search
        self.safety = SafetyGate()
        self.traces = HealthTaskTraceService()

    async def create(
        self,
        user_id: str,
        file: UploadFile,
        document_type: ReportDocumentType = ReportDocumentType.OTHER,
    ) -> ReportResponse:
        retention_days = int(os.getenv("REPORT_IMAGE_RETENTION_DAYS", "30"))
        saved = await self.uploads.save(
            file,
            user_id,
            purpose="report",
            retention_days=retention_days,
        )
        try:
            report_id = str(uuid.uuid4())
            task = self.tasks.create(
                user_id,
                HealthTaskCreate(
                    task_type=TaskType.REPORT_INTERPRETATION,
                    input_snapshot={
                        "upload_filename": saved.filename,
                        "document_type": document_type.value,
                        "report_id": report_id,
                    },
                    expires_at=(
                        datetime.fromisoformat(saved.expires_at)
                        if saved.expires_at
                        else None
                    ),
                ),
            )
            self.db.create_report(
                {
                    "report_id": report_id,
                    "task_id": task.task_id,
                    "user_id": user_id,
                    "upload_filename": saved.filename,
                    "document_type": document_type.value,
                    "status": ReportStatus.UPLOADED.value,
                }
            )
            trace = self.traces.start(
                task, user_id=user_id, operation="report.upload"
            )
            task = set_task_trace(self.tasks, task, user_id, trace.trace_id)
            self.traces.finish(trace, task=task)
        except Exception:
            self.uploads.delete(saved.filename, user_id)
            raise
        return self.get(report_id, user_id)

    def _owned_report(self, report_id: str, user_id: str) -> dict[str, Any]:
        report = self.db.get_report(report_id, user_id)
        if report is None:
            raise ReportNotFoundError(report_id)
        return report

    @staticmethod
    def _measurement_from_row(row: dict[str, Any]) -> ReportMeasurement:
        return ReportMeasurement(
            measurement_id=row["measurement_id"],
            name=row["name"],
            value=row.get("value"),
            unit=row.get("unit"),
            reference_range=row.get("reference_range"),
            abnormal_flag=row.get("abnormal_flag", "unknown"),
            confidence=float(row.get("confidence", 0)),
            raw_text=row.get("raw_text"),
            user_confirmed=bool(row.get("user_confirmed")),
            unable_to_confirm=bool(row.get("unable_to_confirm")),
        )

    def get(self, report_id: str, user_id: str) -> ReportResponse:
        report = self._owned_report(report_id, user_id)
        task = self.tasks.get(report["task_id"], user_id)
        measurements = [
            self._measurement_from_row(row)
            for row in self.db.list_report_measurements(report_id)
        ]
        result = (
            ReportInterpretation.model_validate(task.result)
            if task.result and task.status == TaskStatus.COMPLETED
            else None
        )
        return ReportResponse(
            report_id=report_id,
            task=task,
            document_type=report["document_type"],
            status=report["status"],
            image_url=f"/uploads/{report['upload_filename']}",
            measurements=measurements,
            result=result,
            error=report.get("analysis_error"),
            created_at=report["created_at"],
            updated_at=report["updated_at"],
        )

    def list(self, user_id: str) -> list[ReportResponse]:
        return [self.get(row["report_id"], user_id) for row in self.db.list_reports(user_id)]

    async def analyze(self, report_id: str, user_id: str) -> ReportResponse:
        report = self._owned_report(report_id, user_id)
        current = ReportStatus(report["status"])
        if current in {
            ReportStatus.WAITING_CONFIRMATION,
            ReportStatus.MANUAL_REVIEW,
            ReportStatus.COMPLETED,
        }:
            return self.get(report_id, user_id)
        if current == ReportStatus.ANALYZING:
            return self.get(report_id, user_id)
        if current not in {ReportStatus.UPLOADED, ReportStatus.FAILED}:
            raise ReportStateError("当前报告状态不能开始分析")

        task = self.tasks.get(report["task_id"], user_id)
        trace = self.traces.start(task, user_id=user_id, operation="report.analyze")
        task = set_task_trace(self.tasks, task, user_id, trace.trace_id)
        if task.status in {TaskStatus.CREATED, TaskStatus.FAILED}:
            self.tasks.update(
                task.task_id, user_id, status=TaskStatus.PROCESSING
            )
        self.db.update_report(
            report_id,
            user_id,
            {"status": ReportStatus.ANALYZING.value, "analysis_error": None},
        )
        try:
            draft = await self.analyzer.analyze_report(
                [f"/uploads/{report['upload_filename']}"]
            )
            rows = []
            for measurement in draft.measurements:
                item = measurement.model_dump(mode="json")
                item["measurement_id"] = str(uuid.uuid4())
                rows.append(item)
            self.db.replace_report_measurements(report_id, rows)

            if not rows:
                self.db.update_report(
                    report_id,
                    user_id,
                    {
                        "status": ReportStatus.FAILED.value,
                        "document_type": draft.document_type.value,
                        "analysis_error": "未识别到可确认的指标，请上传更清晰的报告",
                    },
                )
                self.tasks.update(
                    task.task_id,
                    user_id,
                    status=TaskStatus.FAILED,
                    safety_flags=[{"decision": "manual_review"}],
                )
                failed_task = self.tasks.get(report["task_id"], user_id)
                self.traces.finish(
                    trace,
                    task=failed_task,
                    safety_decision="manual_review",
                    error_code="no_measurements",
                )
                return self.get(report_id, user_id)

            report_status = (
                ReportStatus.MANUAL_REVIEW
                if draft.manual_review
                else ReportStatus.WAITING_CONFIRMATION
            )
            self.db.update_report(
                report_id,
                user_id,
                {
                    "status": report_status.value,
                    "document_type": draft.document_type.value,
                    "analysis_error": (
                        "；".join(draft.warnings) if draft.manual_review else None
                    ),
                },
            )
            waiting_task = self.tasks.update(
                task.task_id,
                user_id,
                status=TaskStatus.WAITING_CONFIRMATION,
                result={
                    "draft": {
                        "measurement_count": len(rows),
                        "confidence": draft.confidence,
                        "warnings": draft.warnings,
                    }
                },
                safety_flags=[
                    {
                        "decision": "manual_review"
                        if draft.manual_review
                        else "allow_with_notice"
                    }
                ],
            )
            self.traces.finish(
                trace,
                task=waiting_task,
                safety_decision=(
                    "manual_review" if draft.manual_review else "allow_with_notice"
                ),
            )
        except Exception:
            self.db.update_report(
                report_id,
                user_id,
                {
                    "status": ReportStatus.FAILED.value,
                    "analysis_error": "报告分析失败，请稍后重试",
                },
            )
            current_task = self.tasks.get(report["task_id"], user_id)
            if current_task.status == TaskStatus.PROCESSING:
                self.tasks.update(
                    current_task.task_id,
                    user_id,
                    status=TaskStatus.FAILED,
                )
                current_task = self.tasks.get(report["task_id"], user_id)
            self.traces.finish(
                trace,
                task=current_task,
                error_code="report_analysis_failed",
            )
        return self.get(report_id, user_id)

    @staticmethod
    def _validate_number(value: Optional[str]) -> None:
        if value is None or not _NUMBER_PATTERN.fullmatch(value.strip()):
            raise ValueError("已确认指标必须填写有效数值")

    @staticmethod
    def _calculate_flag(value: Optional[str], reference: Optional[str]) -> AbnormalFlag:
        if not value or not reference:
            return AbnormalFlag.UNKNOWN
        match = _RANGE_PATTERN.fullmatch(reference)
        if not match:
            return AbnormalFlag.UNKNOWN
        try:
            normalized = value.strip().lstrip("<>≤≥").strip()
            current = Decimal(normalized)
            low = Decimal(match.group(1))
            high = Decimal(match.group(2))
        except (InvalidOperation, ValueError):
            return AbnormalFlag.UNKNOWN
        if current < low:
            return AbnormalFlag.LOW
        if current > high:
            return AbnormalFlag.HIGH
        return AbnormalFlag.NORMAL

    def _interpret(
        self, confirmed: List[ReportMeasurement]
    ) -> ReportInterpretation:
        explanations = []
        attention = []
        citations = []
        limitations = [
            "仅解释用户确认的指标，不能替代医生结合症状和病史作出的判断",
            "本功能不提供影像诊断、疾病确诊、处方审核或具体用药调整",
        ]
        knowledge_unavailable = False
        for item in confirmed:
            if item.abnormal_flag in {AbnormalFlag.LOW, AbnormalFlag.HIGH}:
                attention.append(
                    f"{item.name} 超出所填参考范围，建议携原报告咨询医生"
                )
            explanation = {
                "measurement_id": item.measurement_id,
                "name": item.name,
                "summary": f"{item.name} 是报告中的一项检测指标。",
                "range_assessment": (
                    item.abnormal_flag.value
                    if item.reference_range and item.unit
                    else "unknown"
                ),
                "next_step": "结合原报告、症状和医生意见综合判断。",
            }
            try:
                found = self.knowledge_search(item.name, top_k=2)
                if found:
                    explanation["summary"] = found[0].content[:300]
                    for result in found:
                        metadata = result.metadata
                        citations.append(
                            {
                                "doc_id": metadata.get("doc_id") or result.id,
                                "source": metadata.get("source", ""),
                                "title": metadata.get("filename") or metadata.get("disease") or "",
                                "score": result.score,
                            }
                        )
            except KnowledgeUnavailableError:
                knowledge_unavailable = True
            explanations.append(explanation)
        if knowledge_unavailable:
            limitations.append("知识库暂时不可用，本次未附加来源扩展解释")
        unique_citations = {
            str(item.get("doc_id")): item for item in citations if item.get("doc_id")
        }
        safety = self.safety.evaluate(
            SafetyInput(user_confirmed=True, vision_confidence=1)
        )
        return ReportInterpretation(
            confirmed_measurements=[item.model_dump(mode="json") for item in confirmed],
            explanations=explanations,
            medical_attention=attention,
            limitations=limitations,
            citations=list(unique_citations.values()),
            safety_decision=safety.decision.value,
        )

    def confirm(
        self,
        report_id: str,
        user_id: str,
        request: ConfirmMeasurementsRequest,
    ) -> ReportResponse:
        report = self._owned_report(report_id, user_id)
        if ReportStatus(report["status"]) not in {
            ReportStatus.WAITING_CONFIRMATION,
            ReportStatus.MANUAL_REVIEW,
        }:
            raise ReportStateError("当前报告不处于待确认状态")
        task = self.tasks.get(report["task_id"], user_id)
        trace = self.traces.start(task, user_id=user_id, operation="report.confirm")
        task = set_task_trace(self.tasks, task, user_id, trace.trace_id)
        existing = {
            row["measurement_id"]: row
            for row in self.db.list_report_measurements(report_id)
        }
        if any(item.measurement_id not in existing for item in request.measurements):
            raise ReportNotFoundError("Measurement not found")

        for item in request.measurements:
            if item.deleted:
                self.db.delete_report_measurement(item.measurement_id, report_id)
                continue
            if item.user_confirmed:
                self._validate_number(item.value)
            abnormal = self._calculate_flag(item.value, item.reference_range)
            self.db.update_report_measurement(
                item.measurement_id,
                report_id,
                {
                    "name": item.name,
                    "value": item.value,
                    "unit": item.unit,
                    "reference_range": item.reference_range,
                    "abnormal_flag": abnormal.value,
                    "user_confirmed": item.user_confirmed,
                    "unable_to_confirm": item.unable_to_confirm,
                },
            )

        self.db.update_report(
            report_id,
            user_id,
            {"status": ReportStatus.PROCESSING.value, "analysis_error": None},
        )
        self.tasks.update(task.task_id, user_id, status=TaskStatus.PROCESSING)
        confirmed = [
            self._measurement_from_row(row)
            for row in self.db.list_report_measurements(report_id)
            if row.get("user_confirmed") and not row.get("unable_to_confirm")
        ]
        result = self._interpret(confirmed)
        completed_task = self.tasks.update(
            task.task_id,
            user_id,
            status=TaskStatus.COMPLETED,
            result=result.model_dump(mode="json"),
            safety_flags=[{"decision": result.safety_decision}],
        )
        self.db.update_report(
            report_id, user_id, {"status": ReportStatus.COMPLETED.value}
        )
        self.traces.finish(
            trace,
            task=completed_task,
            safety_decision=result.safety_decision,
        )
        return self.get(report_id, user_id)

    async def retry(self, report_id: str, user_id: str) -> ReportResponse:
        report = self._owned_report(report_id, user_id)
        if report["status"] not in {
            ReportStatus.FAILED.value,
            ReportStatus.MANUAL_REVIEW.value,
        }:
            raise ReportStateError("当前报告无需重试")
        self.db.update_report(
            report_id, user_id, {"status": ReportStatus.FAILED.value}
        )
        task = self.tasks.get(report["task_id"], user_id)
        if task.status == TaskStatus.WAITING_CONFIRMATION:
            self.tasks.update(task.task_id, user_id, status=TaskStatus.FAILED)
        return await self.analyze(report_id, user_id)

    def delete(self, report_id: str, user_id: str) -> None:
        report = self._owned_report(report_id, user_id)
        self.db.delete_report(report_id, user_id)
        self.uploads.delete(report["upload_filename"], user_id)
        self.tasks.delete(report["task_id"], user_id)

    def cancel(self, report_id: str, user_id: str) -> ReportResponse:
        report = self._owned_report(report_id, user_id)
        task = self.tasks.get(report["task_id"], user_id)
        if task.status in {
            TaskStatus.COMPLETED,
            TaskStatus.NEEDS_MEDICAL_ATTENTION,
            TaskStatus.CANCELLED,
        }:
            raise ReportStateError("当前报告任务不能取消")
        trace = self.traces.start(task, user_id=user_id, operation="report.cancel")
        task = set_task_trace(self.tasks, task, user_id, trace.trace_id)
        cancelled = self.tasks.cancel(task.task_id, user_id)
        self.db.update_report(
            report_id,
            user_id,
            {"status": ReportStatus.CANCELLED.value, "analysis_error": "任务已取消"},
        )
        self.uploads.delete(report["upload_filename"], user_id)
        self.traces.finish(trace, task=cancelled, error_code="cancelled")
        return self.get(report_id, user_id)

    def recover_stale(self) -> int:
        recovered = 0
        for report in self.db.list_stale_reports():
            self.db.update_report(
                report["report_id"],
                report["user_id"],
                {
                    "status": ReportStatus.FAILED.value,
                    "analysis_error": "服务重启中断了处理，请点击重试",
                },
            )
            task = self.tasks.get(report["task_id"], report["user_id"])
            if task.status == TaskStatus.PROCESSING:
                self.tasks.update(
                    task.task_id,
                    report["user_id"],
                    status=TaskStatus.FAILED,
                )
            recovered += 1
        return recovered
