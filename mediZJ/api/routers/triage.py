"""Consumer symptom self-check endpoints."""

import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from starlette.responses import StreamingResponse

from mediZJ.api.auth import get_current_user
from mediZJ.api.models.task import TaskDeleteResponse
from mediZJ.api.models.triage import (
    TriageAnswerRequest,
    TriageCreateRequest,
    TriageTaskResponse,
)
from mediZJ.api.services.task_service import TaskNotFoundError
from mediZJ.api.services.triage_service import TriageService
from mediZJ.swarm.events import EventType, health_task_event


router = APIRouter(prefix="/api/triage", tags=["triage"])


def get_triage_service() -> TriageService:
    return TriageService()


def _handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, TaskNotFoundError):
        return HTTPException(status_code=404, detail="Task not found")
    return HTTPException(status_code=409, detail=str(exc))


@router.post(
    "/tasks", response_model=TriageTaskResponse, status_code=status.HTTP_201_CREATED
)
async def create_triage(
    request: TriageCreateRequest,
    user: dict = Depends(get_current_user),
    service: TriageService = Depends(get_triage_service),
):
    return await service.create(user["user_id"], request)


@router.post("/tasks/{task_id}/answer", response_model=TriageTaskResponse)
async def answer_triage(
    task_id: str,
    request: TriageAnswerRequest,
    user: dict = Depends(get_current_user),
    service: TriageService = Depends(get_triage_service),
):
    try:
        return await service.answer(task_id, user["user_id"], request)
    except (TaskNotFoundError, ValueError) as exc:
        raise _handle_error(exc) from exc


@router.get("/tasks/{task_id}", response_model=TriageTaskResponse)
async def get_triage(
    task_id: str,
    user: dict = Depends(get_current_user),
    service: TriageService = Depends(get_triage_service),
):
    try:
        return service.get(task_id, user["user_id"])
    except (TaskNotFoundError, ValueError) as exc:
        raise _handle_error(exc) from exc


@router.post("/tasks/{task_id}/stream")
async def stream_triage(
    task_id: str,
    user: dict = Depends(get_current_user),
    service: TriageService = Depends(get_triage_service),
):
    try:
        response = service.get(task_id, user["user_id"])
    except (TaskNotFoundError, ValueError) as exc:
        raise _handle_error(exc) from exc

    async def generate() -> AsyncGenerator[str, None]:
        task = response.task
        started = health_task_event(
            EventType.HEALTH_TASK_STARTED,
            task.task_id,
            task.task_type.value,
            {"status": task.status.value},
        )
        yield json.dumps(
            {"event": started.type.value, "data": started.to_dict()["data"]},
            ensure_ascii=False,
        ) + "\n"
        if response.result:
            risk = health_task_event(
                EventType.HEALTH_RISK_UPDATED,
                task.task_id,
                task.task_type.value,
                {"risk_level": response.result.risk_level.value},
            )
            yield json.dumps(
                {"event": risk.type.value, "data": risk.to_dict()["data"]},
                ensure_ascii=False,
            ) + "\n"
        event_type = (
            EventType.HEALTH_WAITING_CONFIRMATION
            if response.questionnaire
            else EventType.HEALTH_TASK_COMPLETED
        )
        final = health_task_event(
            event_type,
            task.task_id,
            task.task_type.value,
            {"status": task.status.value},
        )
        yield json.dumps(
            {"event": final.type.value, "data": final.to_dict()["data"]},
            ensure_ascii=False,
        ) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.delete("/tasks/{task_id}", response_model=TaskDeleteResponse)
async def delete_triage(
    task_id: str,
    user: dict = Depends(get_current_user),
    service: TriageService = Depends(get_triage_service),
):
    try:
        service.delete(task_id, user["user_id"])
    except (TaskNotFoundError, ValueError) as exc:
        raise _handle_error(exc) from exc
    return TaskDeleteResponse(deleted=True)
