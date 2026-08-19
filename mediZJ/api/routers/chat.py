"""问答路由"""
import asyncio
from fastapi import APIRouter, Depends, Request, UploadFile, File, HTTPException
from starlette.responses import StreamingResponse

from mediZJ.api.models.chat import ChatRequest, ChatResponse, MessageHistory, MessageItem, AnswerRequest, AnswerResponse
from mediZJ.api.services.chat_service import (
    chat_non_stream,
    chat_stream,
    claim_session,
    get_manager,
    session_owner,
)
from mediZJ.api.auth import get_current_user
from mediZJ.api.services.image_upload_service import (
    ImageUploadError,
    ImageUploadService,
)

router = APIRouter(prefix="/api/chat", tags=["chat"])

def _validate_owned_images(images: list[str] | None, user: dict) -> None:
    """确保聊天引用的每张图片都属于当前用户。"""

    if not images:
        return
    service = ImageUploadService()
    for image_url in images:
        try:
            service.ensure_owned(
                image_url,
                user["user_id"],
                is_admin=user["role"] == "admin",
            )
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Image not found")


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user: dict = Depends(get_current_user),
):
    """非流式问答"""
    authenticated_request = request.model_copy(
        update={"user_id": user["user_id"]}
    )
    _validate_owned_images(authenticated_request.images, user)
    if authenticated_request.session_id:
        try:
            claim_session(authenticated_request.session_id, user["user_id"])
        except PermissionError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
    return await chat_non_stream(authenticated_request)


@router.post("/stream")
async def chat_stream_endpoint(
    chat_req: ChatRequest,
    http_request: Request,
    user: dict = Depends(get_current_user),
):
    """流式问答（换行分隔 JSON）"""
    authenticated_request = chat_req.model_copy(
        update={"user_id": user["user_id"]}
    )
    _validate_owned_images(authenticated_request.images, user)
    if authenticated_request.session_id:
        try:
            claim_session(authenticated_request.session_id, user["user_id"])
        except PermissionError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
    return StreamingResponse(
        chat_stream(
            authenticated_request,
            http_request,
        ),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )


@router.post("/answer", response_model=AnswerResponse)
async def submit_answer(
    request: AnswerRequest,
    user: dict = Depends(get_current_user),
):
    """提交问卷答案（用于交互式问诊）

    答案经会话级信号队列传递给正在 interrupt 挂起的 SSE 流，
    由 SSE 内部用 Command(resume=...) 恢复图执行。
    同时保留 QuestionnaireManager.resolve 用于幂等校验（未命中时降级）。
    """
    if session_owner(request.session_id) != user["user_id"]:
        raise HTTPException(status_code=404, detail="Session not found")

    from mediZJ.api.services.session_runtime import put_answer

    if put_answer(request.session_id, request.answers):
        return AnswerResponse(success=True, message="答案已提交")

    # 无活动信号队列（非流式/已清理）：回退到 QuestionnaireManager 兼容逻辑
    manager = get_manager(request.session_id)
    resolved = manager.resolve(request.questionnaire_id, request.answers)
    if resolved:
        return AnswerResponse(success=True, message="答案已提交")
    else:
        return AnswerResponse(success=False, message="未找到对应问卷或问卷已完成")


@router.get("/history/{session_id}", response_model=MessageHistory)
async def get_chat_history(
    session_id: str,
    user: dict = Depends(get_current_user),
):
    """获取会话历史"""
    from mediZJ.memory.short_term import ShortTermMemory
    from mediZJ.memory.session_db import SessionDB

    db = SessionDB()
    session_data = await asyncio.to_thread(
        db.get_session,
        session_id,
        user["user_id"],
    )
    if session_data is None:
        raise HTTPException(status_code=404, detail="Session not found")

    memory = ShortTermMemory()
    raw_messages = await memory.get_recent_messages(session_id=session_id, limit=50)

    # 内存无数据时从 SQLite 加载（同步驱动，下线程执行）
    if not raw_messages:
        raw_messages = [
            {"role": m["role"], "content": m["content"], "timestamp": m.get("timestamp"),
             "images": m.get("images")}
            for m in session_data.get("messages", [])
            if m.get("role") in ("user", "assistant")
        ]

    messages = [
        MessageItem(
            role=msg.get("role", "unknown"),
            content=msg.get("content", ""),
            images=(
                msg.get("images")
                if isinstance(msg.get("images"), list)
                else None
            ),
            timestamp=msg.get("timestamp")
        )
        for msg in raw_messages
    ]

    return MessageHistory(session_id=session_id, messages=messages)


@router.post("/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """上传聊天图片（用于多模态分析）"""
    try:
        saved = await ImageUploadService().save(file, user["user_id"])
    except ImageUploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "url": saved.url,
        "filename": saved.original_name,
        "size": saved.size,
        "content_type": saved.content_type,
    }
