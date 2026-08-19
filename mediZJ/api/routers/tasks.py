"""Unified health-task endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from mediZJ.api.auth import get_current_user
from mediZJ.api.models.task import (
    HealthTaskCreate,
    HealthTaskListResponse,
    HealthTaskResponse,
    InvalidTaskTransition,
    TaskDeleteResponse,
    TaskFeedbackRequest,
    TaskFeedbackResponse,
    TaskStatus,
    TaskType,
)
from mediZJ.api.services.task_service import TaskNotFoundError, TaskService
from mediZJ.evolution import EvolutionService
from loguru import logger


router = APIRouter(prefix="/api/tasks", tags=["health-tasks"])


def get_task_service() -> TaskService:
    return TaskService()


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Task not found")


@router.post("", response_model=HealthTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    request: HealthTaskCreate,
    user: dict = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
):
    return service.create(user["user_id"], request)


@router.get("", response_model=HealthTaskListResponse)
async def list_tasks(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    task_type: Optional[TaskType] = None,
    task_status: Optional[TaskStatus] = Query(default=None, alias="status"),
    user: dict = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
):
    return service.list(
        user["user_id"],
        limit=limit,
        offset=offset,
        task_type=task_type,
        status=task_status,
    )


@router.get("/{task_id}", response_model=HealthTaskResponse)
async def get_task(
    task_id: str,
    user: dict = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
):
    try:
        return service.get(task_id, user["user_id"])
    except TaskNotFoundError as exc:
        raise _not_found() from exc


@router.post("/{task_id}/cancel", response_model=HealthTaskResponse)
async def cancel_task(
    task_id: str,
    user: dict = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
):
    try:
        return service.cancel(task_id, user["user_id"])
    except TaskNotFoundError as exc:
        raise _not_found() from exc
    except InvalidTaskTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/{task_id}", response_model=TaskDeleteResponse)
async def delete_task(
    task_id: str,
    user: dict = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
):
    try:
        service.delete(task_id, user["user_id"])
    except TaskNotFoundError as exc:
        raise _not_found() from exc
    return TaskDeleteResponse(deleted=True)


@router.post("/{task_id}/feedback", response_model=TaskFeedbackResponse)
async def submit_task_feedback(
    task_id: str,
    request: TaskFeedbackRequest,
    user: dict = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
):
    try:
        task = service.get(task_id, user["user_id"])
        feedback = service.db.upsert_health_task_feedback(
            task_id,
            user["user_id"],
            request.rating,
            request.reason_codes,
            request.comment,
        )
        # Only aggregate quality dimensions cross the Evolution boundary.
        # The comment is intentionally not forwarded.
        try:
            EvolutionService().submit_health_task_feedback(
                task_type=task.task_type.value,
                task_status=task.status.value,
                rating=request.rating,
                reason_codes=request.reason_codes,
                safety_decision=(
                    task.safety_flags[-1].get("decision", "")
                    if task.safety_flags
                    else ""
                ),
            )
        except Exception as exc:
            logger.warning("health feedback evolution signal failed: {}", exc)
        return feedback
    except (TaskNotFoundError, LookupError) as exc:
        raise _not_found() from exc
