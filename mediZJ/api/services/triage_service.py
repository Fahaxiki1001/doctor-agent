"""Symptom self-check workflow built on the unified task lifecycle."""

import inspect
import os
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Dict, Optional

from mediZJ.api.models.task import HealthTaskCreate, TaskStatus, TaskType
from mediZJ.api.models.triage import (
    RiskAssessment,
    RiskLevel,
    TriageAnswerRequest,
    TriageCreateRequest,
    TriageTaskResponse,
)
from mediZJ.api.services.safety_service import SafetyGate, SafetyInput
from mediZJ.api.services.task_service import TaskService
from mediZJ.api.services.health_task_trace import (
    HealthTaskTraceService,
    set_task_trace,
)
from mediZJ.api.services.triage_parser import (
    parse_risk_assessment,
    parse_symptom_analysis,
)
from mediZJ.api.services.triage_rules import RED_FLAG_RULES, find_red_flags
from mediZJ.core.skill_loader import load_skill_function


_REQUIRED_ANSWERS = {"duration", "severity", "age", "red_flags"}
_RISK_WEIGHT = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.EMERGENCY: 3,
}

SkillCallable = Callable[[str], Awaitable[Any] | Any]


class TriageService:
    def __init__(
        self,
        task_service: Optional[TaskService] = None,
        safety_gate: Optional[SafetyGate] = None,
        risk_skill: Optional[SkillCallable] = None,
        symptom_skill: Optional[SkillCallable] = None,
        trace_service: Optional[HealthTaskTraceService] = None,
    ):
        self.tasks = task_service or TaskService()
        self.safety = safety_gate or SafetyGate()
        self._risk_skill = risk_skill
        self._symptom_skill = symptom_skill
        self.traces = trace_service or HealthTaskTraceService()

    @staticmethod
    def _questionnaire(task_id: str) -> Dict[str, Any]:
        return {
            "questionnaire_id": f"triage-{task_id}",
            "questions": [
                {
                    "id": "duration",
                    "text": "症状持续多久了？",
                    "type": "input",
                    "required": True,
                },
                {
                    "id": "severity",
                    "text": "目前严重程度如何？",
                    "type": "enum",
                    "required": True,
                    "options": ["轻微", "中等", "严重"],
                },
                {
                    "id": "age",
                    "text": "患者年龄是多少？",
                    "type": "number",
                    "required": True,
                },
                {
                    "id": "red_flags",
                    "text": "是否有胸痛、呼吸困难、意识改变等危险信号？",
                    "type": "multi",
                    "required": True,
                    "options": [rule.label for rule in RED_FLAG_RULES] + ["均无"],
                },
                {
                    "id": "conditions",
                    "text": "有哪些基础病？",
                    "type": "input",
                    "required": False,
                },
                {
                    "id": "medications",
                    "text": "目前在使用哪些药物？",
                    "type": "input",
                    "required": False,
                },
                {
                    "id": "special_population",
                    "text": "是否为儿童、孕妇或高龄老人？",
                    "type": "input",
                    "required": False,
                },
            ],
        }

    @staticmethod
    def _input_texts(snapshot: Dict[str, Any]) -> list[str]:
        answers = snapshot.get("answers") or {}
        flattened = [snapshot.get("symptom", "")]
        for value in answers.values():
            if isinstance(value, list):
                flattened.extend(str(item) for item in value)
            else:
                flattened.append(str(value))
        return flattened

    def _emergency_result(self, hits: list[dict[str, str]]) -> RiskAssessment:
        return RiskAssessment(
            risk_level=RiskLevel.EMERGENCY,
            urgency="请立即呼叫 120 或前往急诊",
            confidence=1,
            key_findings=[hit["label"] for hit in hits],
            red_flags_checked=[rule.label for rule in RED_FLAG_RULES],
            red_flags_found=[hit["label"] for hit in hits],
            next_steps=list(dict.fromkeys(hit["action"] for hit in hits)),
            limitations=["线上自测不能替代现场急救和医生评估"],
        )

    def _assess(self, snapshot: Dict[str, Any]) -> RiskAssessment:
        answers = snapshot.get("answers") or {}
        severity = str(answers.get("severity", ""))
        age_value = answers.get("age")
        try:
            age = int(age_value) if age_value is not None else -1
        except (TypeError, ValueError):
            age = -1

        special = str(answers.get("special_population", ""))
        conditions = str(answers.get("conditions", ""))
        if "严重" in severity:
            risk = RiskLevel.HIGH
            urgency = "建议今天内尽快就医评估"
            confidence = 0.82
        elif age < 0:
            risk = RiskLevel.MEDIUM
            urgency = "信息不足，建议补充年龄或咨询医务人员"
            confidence = 0.45
        elif age < 6 or age >= 75 or special or conditions:
            risk = RiskLevel.MEDIUM
            urgency = "建议 24 小时内咨询医生；加重时提前就医"
            confidence = 0.72
        else:
            risk = RiskLevel.LOW
            urgency = "可先观察并进行一般护理，持续或加重时就医"
            confidence = 0.76

        return RiskAssessment(
            risk_level=risk,
            urgency=urgency,
            confidence=confidence,
            key_findings=[
                f"主要不适：{snapshot.get('symptom', '')}",
                f"持续时间：{answers.get('duration', '未提供')}",
                f"严重程度：{severity or '未提供'}",
            ],
            red_flags_checked=[rule.label for rule in RED_FLAG_RULES],
            red_flags_found=[],
            next_steps=[
                "记录症状变化、体温及诱发因素",
                "若出现胸痛、呼吸困难、意识改变、大出血等情况立即呼叫 120",
            ],
            limitations=["该结果是风险分层而非疾病诊断，不能替代面诊和必要检查"],
        )

    @staticmethod
    async def _call_skill(skill: SkillCallable, text: str) -> Any:
        result = skill(text)
        return await result if inspect.isawaitable(result) else result

    def _load_skills(self) -> tuple[SkillCallable, SkillCallable]:
        if self._risk_skill is None:
            self._risk_skill = load_skill_function("assess-risk", "risk", "assess_risk")
        if self._symptom_skill is None:
            self._symptom_skill = load_skill_function(
                "analyze-symptoms", "symptoms", "analyze_symptoms"
            )
        return self._risk_skill, self._symptom_skill

    async def _assess_with_skills(self, snapshot: Dict[str, Any]) -> RiskAssessment:
        """Merge both legacy Skills into the strict triage result conservatively."""

        fallback = self._assess(snapshot)
        text = "；".join(self._input_texts(snapshot))
        try:
            risk_skill, symptom_skill = self._load_skills()
            risk_raw = await self._call_skill(risk_skill, text)
            symptom_raw = await self._call_skill(symptom_skill, text)
        except Exception:
            # A broken or unavailable Skill is itself insufficient information.
            return parse_risk_assessment(None)

        skill_result = parse_risk_assessment(risk_raw)
        selected = max(
            (fallback, skill_result), key=lambda item: _RISK_WEIGHT[item.risk_level]
        )
        symptom_result = parse_symptom_analysis(symptom_raw)
        if symptom_result is None:
            return parse_risk_assessment(None)
        patterns = [str(item)[:200] for item in symptom_result.patterns[:5] if item]

        return selected.model_copy(
            update={
                "key_findings": list(
                    dict.fromkeys([*fallback.key_findings, *patterns])
                ),
                "red_flags_checked": [rule.label for rule in RED_FLAG_RULES],
                "red_flags_found": [],
                "limitations": list(
                    dict.fromkeys(
                        [
                            *selected.limitations,
                            "症状模式仅用于风险分层，不展示或生成疾病确诊结论",
                        ]
                    )
                ),
            }
        )

    async def _finish_or_collect(
        self, task_id: str, user_id: str
    ) -> TriageTaskResponse:
        task = self.tasks.get(task_id, user_id)
        trace = self.traces.start(task, user_id=user_id, operation="triage.assess")
        task = set_task_trace(self.tasks, task, user_id, trace.trace_id)

        def complete(response: TriageTaskResponse) -> TriageTaskResponse:
            risk, safety = self.traces.risk_and_safety(response.task)
            self.traces.finish(
                trace,
                task=response.task,
                risk_level=risk,
                safety_decision=safety,
            )
            return response

        snapshot = task.input_snapshot
        try:
            hits = find_red_flags(self._input_texts(snapshot))
            if hits:
                result = self._emergency_result(hits)
                safety = self.safety.evaluate(
                    SafetyInput(
                        user_text=" ".join(self._input_texts(snapshot)),
                        rule_result={"risk_level": "emergency"},
                    )
                )
                task = self.tasks.update(
                    task_id,
                    user_id,
                    status=TaskStatus.NEEDS_MEDICAL_ATTENTION,
                    result=result.model_dump(mode="json"),
                    safety_flags=[
                        {"code": hit["code"], "reason": hit["label"]} for hit in hits
                    ]
                    + [{"decision": safety.decision.value}],
                )
                return complete(TriageTaskResponse(task=task, result=result))

            answers = snapshot.get("answers") or {}
            if not _REQUIRED_ANSWERS.issubset(answers):
                target = (
                    TaskStatus.COLLECTING
                    if task.status == TaskStatus.CREATED
                    else task.status
                )
                if target != task.status:
                    task = self.tasks.update(task_id, user_id, status=target)
                return complete(
                    TriageTaskResponse(
                        task=task, questionnaire=self._questionnaire(task_id)
                    )
                )

            if task.status in {TaskStatus.CREATED, TaskStatus.COLLECTING}:
                task = self.tasks.update(task_id, user_id, status=TaskStatus.PROCESSING)
            result = await self._assess_with_skills(snapshot)
            safety = self.safety.evaluate(
                SafetyInput(llm_result={"risk_level": result.risk_level.value})
            )
            final_status = (
                TaskStatus.NEEDS_MEDICAL_ATTENTION
                if result.risk_level in {RiskLevel.HIGH, RiskLevel.EMERGENCY}
                else TaskStatus.COMPLETED
            )
            task = self.tasks.update(
                task_id,
                user_id,
                status=final_status,
                result=result.model_dump(mode="json"),
                safety_flags=[{"decision": safety.decision.value}],
            )
            return complete(TriageTaskResponse(task=task, result=result))
        except Exception as exc:
            self.traces.finish(trace, task=task, error=exc)
            raise

    async def create(
        self, user_id: str, request: TriageCreateRequest
    ) -> TriageTaskResponse:
        task = self.tasks.create(
            user_id,
            HealthTaskCreate(
                task_type=TaskType.TRIAGE,
                session_id=request.session_id,
                input_snapshot={
                    "symptom": request.symptom,
                    "answers": request.answers,
                    "answered_questionnaires": [],
                },
                # A questionnaire is an interactive task; do not leave an
                # abandoned draft indefinitely in collecting state.
                expires_at=datetime.now() + timedelta(
                    minutes=int(os.getenv("TRIAGE_TASK_TIMEOUT_MINUTES", "30"))
                ),
            ),
        )
        return await self._finish_or_collect(task.task_id, user_id)

    async def answer(
        self, task_id: str, user_id: str, request: TriageAnswerRequest
    ) -> TriageTaskResponse:
        task = self.tasks.get(task_id, user_id)
        if task.task_type != TaskType.TRIAGE:
            raise ValueError("Task is not a triage task")
        if (
            task.expires_at is not None
            and task.expires_at <= datetime.now(task.expires_at.tzinfo)
            and task.status in {TaskStatus.CREATED, TaskStatus.COLLECTING}
        ):
            trace = self.traces.start(task, user_id=user_id, operation="triage.timeout")
            task = set_task_trace(self.tasks, task, user_id, trace.trace_id)
            failed = self.tasks.update(
                task_id,
                user_id,
                status=TaskStatus.FAILED,
                safety_flags=[{"decision": "manual_review", "code": "timeout"}],
            )
            self.traces.finish(trace, task=failed, error_code="timeout")
            return self.get(task_id, user_id)
        if task.status not in {TaskStatus.CREATED, TaskStatus.COLLECTING}:
            trace = self.traces.start(task, user_id=user_id, operation="triage.resume")
            task = set_task_trace(self.tasks, task, user_id, trace.trace_id)
            self.traces.finish(
                trace,
                task=task,
                risk_level=(task.result or {}).get("risk_level", ""),
                safety_decision=(task.safety_flags[-1].get("decision", "")
                                 if task.safety_flags else ""),
            )
            return self.get(task_id, user_id)
        snapshot = dict(task.input_snapshot)
        answered = list(snapshot.get("answered_questionnaires") or [])
        if request.questionnaire_id in answered:
            return self.get(task_id, user_id)
        expected_id = self._questionnaire(task_id)["questionnaire_id"]
        if request.questionnaire_id != expected_id:
            raise ValueError("Questionnaire does not belong to this task")
        snapshot["answers"] = {
            **(snapshot.get("answers") or {}),
            **request.answers,
        }
        if _REQUIRED_ANSWERS.issubset(snapshot["answers"]):
            answered.append(request.questionnaire_id)
        snapshot["answered_questionnaires"] = answered
        self.tasks.update(task_id, user_id, input_snapshot=snapshot)
        return await self._finish_or_collect(task_id, user_id)

    def get(self, task_id: str, user_id: str) -> TriageTaskResponse:
        task = self.tasks.get(task_id, user_id)
        if task.task_type != TaskType.TRIAGE:
            raise ValueError("Task is not a triage task")
        result = RiskAssessment.model_validate(task.result) if task.result else None
        questionnaire = (
            self._questionnaire(task_id)
            if task.status == TaskStatus.COLLECTING
            else None
        )
        return TriageTaskResponse(task=task, questionnaire=questionnaire, result=result)

    def delete(self, task_id: str, user_id: str) -> None:
        task = self.tasks.get(task_id, user_id)
        if task.task_type != TaskType.TRIAGE:
            raise ValueError("Task is not a triage task")
        self.tasks.delete(task_id, user_id)
