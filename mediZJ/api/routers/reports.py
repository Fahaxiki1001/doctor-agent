"""Medical report interpretation endpoints."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from mediZJ.api.auth import get_current_user
from mediZJ.api.models.report import (
    ConfirmMeasurementsRequest,
    ReportDocumentType,
    ReportResponse,
)
from mediZJ.api.models.task import TaskDeleteResponse
from mediZJ.api.services.image_upload_service import ImageUploadError
from mediZJ.api.services.report_service import (
    ReportNotFoundError,
    ReportService,
    ReportStateError,
)


router = APIRouter(prefix="/api/reports", tags=["reports"])


def get_report_service() -> ReportService:
    return ReportService()


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ReportNotFoundError):
        return HTTPException(status_code=404, detail="Report not found")
    if isinstance(exc, ImageUploadError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=409, detail=str(exc))


@router.post("", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def upload_report(
    file: UploadFile = File(...),
    document_type: ReportDocumentType = Form(ReportDocumentType.OTHER),
    user: dict = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
):
    try:
        return await service.create(user["user_id"], file, document_type)
    except (ImageUploadError, ValueError) as exc:
        raise _http_error(exc) from exc


@router.get("", response_model=list[ReportResponse])
async def list_reports(
    user: dict = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
):
    return service.list(user["user_id"])


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: str,
    user: dict = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
):
    try:
        return service.get(report_id, user["user_id"])
    except ReportNotFoundError as exc:
        raise _http_error(exc) from exc


@router.get("/{report_id}/draft", response_model=ReportResponse)
async def get_report_draft(
    report_id: str,
    user: dict = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
):
    try:
        return service.get(report_id, user["user_id"])
    except ReportNotFoundError as exc:
        raise _http_error(exc) from exc


@router.get("/{report_id}/result", response_model=ReportResponse)
async def get_report_result(
    report_id: str,
    user: dict = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
):
    try:
        response = service.get(report_id, user["user_id"])
    except ReportNotFoundError as exc:
        raise _http_error(exc) from exc
    if response.result is None:
        raise HTTPException(status_code=409, detail="报告解读尚未完成")
    return response


@router.post("/{report_id}/analyze", response_model=ReportResponse)
async def analyze_report(
    report_id: str,
    user: dict = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
):
    try:
        return await service.analyze(report_id, user["user_id"])
    except (ReportNotFoundError, ReportStateError) as exc:
        raise _http_error(exc) from exc


@router.put("/{report_id}/measurements/confirm", response_model=ReportResponse)
async def confirm_measurements(
    report_id: str,
    request: ConfirmMeasurementsRequest,
    user: dict = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
):
    try:
        return service.confirm(report_id, user["user_id"], request)
    except (ReportNotFoundError, ReportStateError, ValueError) as exc:
        raise _http_error(exc) from exc


@router.post("/{report_id}/retry", response_model=ReportResponse)
async def retry_report(
    report_id: str,
    user: dict = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
):
    try:
        return await service.retry(report_id, user["user_id"])
    except (ReportNotFoundError, ReportStateError) as exc:
        raise _http_error(exc) from exc


@router.post("/{report_id}/cancel", response_model=ReportResponse)
async def cancel_report(
    report_id: str,
    user: dict = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
):
    try:
        return service.cancel(report_id, user["user_id"])
    except (ReportNotFoundError, ReportStateError) as exc:
        raise _http_error(exc) from exc


@router.delete("/{report_id}", response_model=TaskDeleteResponse)
async def delete_report(
    report_id: str,
    user: dict = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
):
    try:
        service.delete(report_id, user["user_id"])
    except ReportNotFoundError as exc:
        raise _http_error(exc) from exc
    return TaskDeleteResponse(deleted=True)
