"""知识库路由"""
import threading
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form

from mediZJ.api.models.knowledge import (
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeTypesResponse,
    DocumentListResponse,
    DocumentChunksResponse,
    DocumentUploadResponse,
    DocumentDeleteResponse,
    DocumentUpdateRequest,
    KnowledgeDocumentPreview,
    ContinueChatRequest,
    ContinueChatResponse,
)
from mediZJ.api.services.knowledge_service import (
    search_knowledge_for_user, get_knowledge_types,
    get_consumer_knowledge_categories,
    list_all_documents, get_document_chunks,
    delete_document, upload_document, update_document,
    get_document_preview, KnowledgeUnavailableError,
)
from mediZJ.api.auth import get_current_user, require_admin
from mediZJ.api.models.task import TaskType
from mediZJ.api.routers.tasks import get_task_service
from mediZJ.api.services.task_service import TaskNotFoundError, TaskService

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

_search_windows: dict[str, deque[float]] = defaultdict(deque)
_search_lock = threading.Lock()


def _check_search_rate(user_id: str, limit: int = 30) -> None:
    now = time.monotonic()
    with _search_lock:
        window = _search_windows[user_id]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= limit:
            raise HTTPException(status_code=429, detail="搜索过于频繁，请稍后再试")
        window.append(now)


@router.post("/search", response_model=KnowledgeSearchResponse)
async def search(
    request: KnowledgeSearchRequest,
    user: dict = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
):
    """搜索知识库"""
    _check_search_rate(user["user_id"])
    try:
        results, search_id = search_knowledge_for_user(
            user_id=user["user_id"],
            query=request.query.strip(),
            top_k=request.top_k,
            filter_type=request.filter_type,
            task_service=task_service,
        )
    except KnowledgeUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return KnowledgeSearchResponse(
        results=results,
        total=len(results),
        query=request.query.strip(),
        search_id=search_id,
        task_id=search_id,
        category=request.filter_type,
    )


@router.get("/types", response_model=KnowledgeTypesResponse)
async def get_types():
    """获取知识库类型列表"""
    types = get_knowledge_types()
    return KnowledgeTypesResponse(types=types)


@router.get("/categories", response_model=KnowledgeTypesResponse)
async def get_categories():
    """Consumer-facing category list."""
    return KnowledgeTypesResponse(types=get_consumer_knowledge_categories())


@router.get("/documents", response_model=DocumentListResponse)
async def get_documents(_admin: dict = Depends(require_admin)):
    """获取知识库文档列表"""
    return list_all_documents()


@router.get("/documents/{doc_id:path}/chunks", response_model=DocumentChunksResponse)
async def get_chunks(doc_id: str, _admin: dict = Depends(require_admin)):
    """获取文档的所有分块"""
    result = get_document_chunks(doc_id)
    if result.total == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    return result


@router.get(
    "/documents/{doc_id:path}/preview",
    response_model=KnowledgeDocumentPreview,
)
async def preview_document(doc_id: str):
    """Read-only source preview for consumer search results."""
    try:
        return get_document_preview(doc_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    except KnowledgeUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/searches/{search_id}/continue-chat",
    response_model=ContinueChatResponse,
)
async def continue_chat(
    search_id: str,
    request: ContinueChatRequest,
    user: dict = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
):
    """Build chat context only from references returned by this owned search."""
    try:
        task = task_service.get(search_id, user["user_id"])
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Search not found") from exc
    if task.task_type != TaskType.KNOWLEDGE_SEARCH:
        raise HTTPException(status_code=404, detail="Search not found")
    sources = task.result.get("sources") or []
    by_id = {source.get("doc_id"): source for source in sources}
    if any(doc_id not in by_id for doc_id in request.document_ids):
        raise HTTPException(status_code=404, detail="Source not found")
    selected = [by_id[doc_id] for doc_id in request.document_ids]
    return ContinueChatResponse(
        context={
            "knowledge_search_id": search_id,
            "task_id": search_id,
            "task_type": "knowledge_search",
            "status": task.status.value,
            "query": task.result.get("query", ""),
            "citations": selected,
        }
    )


@router.delete("/documents/{doc_id:path}", response_model=DocumentDeleteResponse)
async def remove_document(
    doc_id: str,
    _admin: dict = Depends(require_admin),
):
    """删除文档"""
    result = delete_document(doc_id)
    if result.chunks_deleted == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    return result


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    doc_type: str = Form("general"),
    disease: str = Form(""),
    source: str = Form("用户上传"),
    version: str | None = Form(None),
    published_at: str | None = Form(None),
    reviewed_at: str | None = Form(None),
    applicable_population: str | None = Form(None),
    _admin: dict = Depends(require_admin),
):
    """上传文件到知识库"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "txt"

    if ext != "txt":
        raise HTTPException(status_code=400, detail=f"暂不支持 .{ext} 格式，目前仅支持 .txt 文件")

    try:
        raw = await file.read()
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="文件必须为 UTF-8 编码")

    if not content.strip():
        raise HTTPException(status_code=400, detail="文件内容为空")

    try:
        return upload_document(
            filename=file.filename,
            content=content,
            doc_type=doc_type,
            disease=disease,
            source=source,
            version=version,
            published_at=published_at,
            reviewed_at=reviewed_at,
            applicable_population=applicable_population,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/documents/{doc_id:path}", response_model=DocumentUploadResponse)
async def update_doc(
    doc_id: str,
    request: DocumentUpdateRequest,
    _admin: dict = Depends(require_admin),
):
    """更新文档内容"""
    try:
        return update_document(
            doc_id=doc_id,
            content=request.content,
            doc_type=request.type,
            disease=request.disease,
            source=request.source,
            version=request.version,
            published_at=request.published_at,
            reviewed_at=request.reviewed_at,
            applicable_population=request.applicable_population,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
