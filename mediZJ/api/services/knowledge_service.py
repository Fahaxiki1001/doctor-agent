"""知识库服务：封装 MedicalKnowledgeBase 搜索"""
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from loguru import logger

from mediZJ.knowledge.milvus_kb import MedicalKnowledgeBase
from mediZJ.api.models.knowledge import (
    KnowledgeItem, KnowledgeTypeInfo,
    DocumentSummary, DocumentListResponse,
    ChunkDetail, DocumentChunksResponse,
    DocumentUploadResponse, DocumentDeleteResponse,
    KnowledgeDocumentPreview,
)

from mediZJ.api.models.task import HealthTaskCreate, TaskStatus, TaskType
from mediZJ.api.services.task_service import TaskService
from mediZJ.api.services.health_task_trace import (
    HealthTaskTraceService,
    set_task_trace,
)


# 知识库类型定义
KNOWLEDGE_TYPES = [
    KnowledgeTypeInfo(
        key="lifestyle",
        label="生活方式",
        description="饮食、运动、睡眠、用药等生活方式建议"
    ),
    KnowledgeTypeInfo(
        key="symptoms",
        label="症状处理",
        description="急症症状识别与处理指南"
    ),
    KnowledgeTypeInfo(
        key="disease_classification",
        label="疾病编码",
        description="ICD-10 疾病分类与编码"
    ),
    KnowledgeTypeInfo(
        key="clinical_guideline",
        label="临床指南",
        description="临床诊疗指南和专家共识"
    ),
]

CONSUMER_KNOWLEDGE_CATEGORIES = [
    KnowledgeTypeInfo(
        key="symptoms",
        label="疾病与症状",
        description="常见疾病症状、危险信号和就医提示",
    ),
    KnowledgeTypeInfo(
        key="lab_indicator",
        label="检查指标",
        description="常见检验指标的含义和参考信息",
    ),
    KnowledgeTypeInfo(
        key="lifestyle",
        label="生活方式",
        description="饮食、运动、睡眠等健康管理建议",
    ),
    KnowledgeTypeInfo(
        key="clinical_guideline",
        label="临床指南",
        description="临床诊疗指南和专家共识",
    ),
]


class KnowledgeUnavailableError(RuntimeError):
    """The retrieval backend cannot serve a trustworthy response."""


def search_knowledge(
    query: str,
    top_k: int = 5,
    filter_type: Optional[str] = None
) -> List[KnowledgeItem]:
    """搜索知识库"""
    try:
        kb = MedicalKnowledgeBase()
        results = kb.search(
            query=query,
            top_k=top_k,
            filter_type=filter_type
        )
        return [
            KnowledgeItem(
                id=str(r.get("id", "")),
                content=r.get("content", ""),
                metadata=r.get("metadata", {}),
                score=r.get("score", 0.0)
            )
            for r in results
        ]
    except Exception as e:
        logger.error(f"Knowledge search error: {e}")
        raise KnowledgeUnavailableError("知识库暂时不可用，请稍后重试") from e


def search_knowledge_for_user(
    user_id: str,
    query: str,
    top_k: int = 5,
    filter_type: Optional[str] = None,
    task_service: Optional[TaskService] = None,
) -> tuple[List[KnowledgeItem], str]:
    """Search, de-duplicate by doc_id and persist a content-light task snapshot."""
    tasks = task_service or TaskService()
    task = tasks.create(
        user_id,
        HealthTaskCreate(
            task_type=TaskType.KNOWLEDGE_SEARCH,
            input_snapshot={"query": query, "category": filter_type},
        ),
    )
    traces = HealthTaskTraceService()
    trace = traces.start(task, user_id=user_id, operation="knowledge.search")
    task = set_task_trace(tasks, task, user_id, trace.trace_id)
    try:
        tasks.update(task.task_id, user_id, status=TaskStatus.PROCESSING)
        results = search_knowledge(query, top_k, filter_type)
    except Exception as exc:
        failed = tasks.update(
            task.task_id,
            user_id,
            status=TaskStatus.FAILED,
            result={"query": query, "category": filter_type, "total": 0},
        )
        traces.finish(trace, task=failed, error=exc, error_code="knowledge_unavailable")
        raise

    deduplicated: List[KnowledgeItem] = []
    seen: set[str] = set()
    for item in results:
        doc_id = str(item.metadata.get("doc_id") or item.id)
        if not doc_id or doc_id in seen:
            continue
        seen.add(doc_id)
        deduplicated.append(item)

    source_snapshot = []
    for item in deduplicated:
        metadata = item.metadata
        source_snapshot.append(
            {
                "doc_id": str(metadata.get("doc_id") or item.id),
                "score": item.score,
                "source": metadata.get("source", ""),
                "title": metadata.get("filename") or metadata.get("disease") or "",
                "type": metadata.get("type", ""),
                "snippet": item.content[:240],
                "published_at": metadata.get("published_at"),
                "reviewed_at": metadata.get("reviewed_at"),
                "applicable_population": metadata.get("applicable_population"),
            }
        )
    tasks.update(
        task.task_id,
        user_id,
        status=TaskStatus.PROCESSING,
    )
    completed = tasks.update(
        task.task_id,
        user_id,
        status=TaskStatus.COMPLETED,
        result={
            "query": query,
            "category": filter_type,
            "sources": source_snapshot,
            "total": len(source_snapshot),
        },
    )
    traces.finish(trace, task=completed)
    return deduplicated, task.task_id


def get_document_preview(doc_id: str) -> KnowledgeDocumentPreview:
    chunks = get_document_chunks(doc_id)
    if not chunks.chunks:
        raise LookupError(doc_id)
    metadata: Dict[str, Any] = {}
    try:
        kb = MedicalKnowledgeBase()
        raw_chunks = kb.get_document_chunks(doc_id)
        if raw_chunks:
            metadata = raw_chunks[0].get("metadata", {})
    except Exception as exc:
        raise KnowledgeUnavailableError("知识库暂时不可用，请稍后重试") from exc
    return KnowledgeDocumentPreview(
        doc_id=doc_id,
        title=metadata.get("filename") or metadata.get("disease") or doc_id,
        source=metadata.get("source", ""),
        type=metadata.get("type", ""),
        disease=metadata.get("disease", ""),
        version=metadata.get("version"),
        published_at=metadata.get("published_at"),
        reviewed_at=metadata.get("reviewed_at"),
        applicable_population=metadata.get("applicable_population"),
        content="\n".join(chunk.content for chunk in chunks.chunks),
    )


def get_knowledge_types() -> List[KnowledgeTypeInfo]:
    """获取知识库类型列表"""
    return KNOWLEDGE_TYPES


def get_consumer_knowledge_categories() -> List[KnowledgeTypeInfo]:
    """Return consumer labels without exposing operator taxonomy."""
    return CONSUMER_KNOWLEDGE_CATEGORIES


def get_knowledge_base_size() -> int:
    """获取知识库文档数量"""
    try:
        kb = MedicalKnowledgeBase()
        return kb.count_documents()
    except Exception:
        return 0


def list_all_documents() -> DocumentListResponse:
    """获取知识库文档列表"""
    kb = MedicalKnowledgeBase()
    docs = kb.list_documents()
    summaries = [DocumentSummary(**d) for d in docs]
    return DocumentListResponse(documents=summaries, total=len(summaries))


def get_document_chunks(doc_id: str) -> DocumentChunksResponse:
    """获取文档的所有分块"""
    kb = MedicalKnowledgeBase()
    chunks = kb.get_document_chunks(doc_id)
    details = [ChunkDetail(**c) for c in chunks]
    return DocumentChunksResponse(doc_id=doc_id, chunks=details, total=len(details))


def delete_document(doc_id: str) -> DocumentDeleteResponse:
    """删除文档"""
    kb = MedicalKnowledgeBase()
    count = kb.delete_document(doc_id)
    return DocumentDeleteResponse(doc_id=doc_id, chunks_deleted=count)


def upload_document(
    filename: str,
    content: str,
    doc_type: str = "general",
    disease: str = "",
    source: str = "用户上传",
    version: Optional[str] = None,
    published_at: Optional[str] = None,
    reviewed_at: Optional[str] = None,
    applicable_population: Optional[str] = None,
) -> DocumentUploadResponse:
    """上传文档到知识库"""
    content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
    safe_name = re.sub(r'[^\w]', '_', Path(filename).stem)
    doc_id = f"{doc_type}_{safe_name}"

    kb = MedicalKnowledgeBase()

    if kb.document_exists_by_hash(content_hash):
        raise ValueError(f"内容相同的文档已存在: {filename}")

    metadata = {
        "type": doc_type,
        "disease": disease or safe_name,
        "source": source,
        "filename": filename,
        "content_hash": content_hash,
        "version": version or "",
        "published_at": published_at or "",
        "reviewed_at": reviewed_at or "",
        "applicable_population": applicable_population or "",
    }
    doc = {"id": doc_id, "content": content, "metadata": metadata}
    chunks_added = kb.add_documents([doc])

    return DocumentUploadResponse(
        doc_id=doc_id,
        filename=filename,
        type=doc_type,
        chunks_added=chunks_added,
    )


def update_document(
    doc_id: str,
    content: str,
    doc_type: Optional[str] = None,
    disease: Optional[str] = None,
    source: Optional[str] = None,
    version: Optional[str] = None,
    published_at: Optional[str] = None,
    reviewed_at: Optional[str] = None,
    applicable_population: Optional[str] = None,
) -> DocumentUploadResponse:
    """更新知识库文档"""
    kb = MedicalKnowledgeBase()

    existing = kb.get_document_chunks(doc_id)
    if not existing:
        raise ValueError(f"Document not found: {doc_id}")

    # 从已有 chunk 获取原始元数据
    old_meta_row = kb.milvus_client.query(
        collection_name=kb.collection_name,
        filter=f'doc_id == "{doc_id}"',
        output_fields=["doc_type", "disease", "source", "filename", "version",
                       "published_at", "reviewed_at", "applicable_population"],
        limit=1
    )
    old_meta = old_meta_row[0] if old_meta_row else {}

    metadata = {
        "type": doc_type or old_meta.get("doc_type", "general"),
        "disease": disease or old_meta.get("disease", ""),
        "source": source or old_meta.get("source", "用户上传"),
        "filename": old_meta.get("filename", ""),
        "version": version if version is not None else old_meta.get("version", ""),
        "published_at": published_at if published_at is not None else old_meta.get("published_at", ""),
        "reviewed_at": reviewed_at if reviewed_at is not None else old_meta.get("reviewed_at", ""),
        "applicable_population": (
            applicable_population
            if applicable_population is not None
            else old_meta.get("applicable_population", "")
        ),
    }

    chunks_added = kb.update_document(doc_id, content, metadata)
    return DocumentUploadResponse(
        doc_id=doc_id,
        filename=metadata["filename"],
        type=metadata["type"],
        chunks_added=chunks_added,
        message="updated",
    )
