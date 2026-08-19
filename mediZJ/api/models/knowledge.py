"""知识库接口的请求/响应模型"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class KnowledgeSearchRequest(BaseModel):
    """知识库搜索请求"""
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)
    filter_type: Optional[str] = None  # lifestyle / symptoms / disease_classification / clinical_guideline


class KnowledgeItem(BaseModel):
    """知识条目"""
    id: str
    content: str
    metadata: Dict[str, Any] = {}
    score: float = 0.0


class KnowledgeSearchResponse(BaseModel):
    """知识库搜索响应"""
    results: List[KnowledgeItem] = []
    total: int = 0
    query: str = ""
    search_id: str = ""
    task_id: str = ""
    category: Optional[str] = None


class KnowledgeTypeInfo(BaseModel):
    """知识库类型信息"""
    key: str
    label: str
    description: str


class KnowledgeTypesResponse(BaseModel):
    """知识库类型列表响应"""
    types: List[KnowledgeTypeInfo] = []


class DocumentSummary(BaseModel):
    """文档摘要（列表项）"""
    doc_id: str
    filename: str
    type: str
    disease: str
    source: str
    chunk_count: int
    version: Optional[str] = None
    published_at: Optional[str] = None
    reviewed_at: Optional[str] = None
    applicable_population: Optional[str] = None


class DocumentListResponse(BaseModel):
    """文档列表响应"""
    documents: List[DocumentSummary] = []
    total: int = 0


class ChunkDetail(BaseModel):
    """文档块详情"""
    milvus_id: int
    chunk_id: int
    content: str
    total_chunks: int


class DocumentChunksResponse(BaseModel):
    """文档块列表响应"""
    doc_id: str
    chunks: List[ChunkDetail] = []
    total: int = 0


class DocumentUploadResponse(BaseModel):
    """文件上传响应"""
    doc_id: str
    filename: str
    type: str
    chunks_added: int
    message: str = "ok"


class DocumentDeleteResponse(BaseModel):
    """文件删除响应"""
    doc_id: str
    chunks_deleted: int
    message: str = "ok"


class DocumentUpdateRequest(BaseModel):
    """文档更新请求"""
    content: str
    type: Optional[str] = None
    disease: Optional[str] = None
    source: Optional[str] = None
    version: Optional[str] = None
    published_at: Optional[str] = None
    reviewed_at: Optional[str] = None
    applicable_population: Optional[str] = None


class KnowledgeDocumentPreview(BaseModel):
    doc_id: str
    title: str = ""
    source: str = ""
    type: str = ""
    disease: str = ""
    version: Optional[str] = None
    published_at: Optional[str] = None
    reviewed_at: Optional[str] = None
    applicable_population: Optional[str] = None
    content: str = ""


class ContinueChatRequest(BaseModel):
    document_ids: List[str] = Field(min_length=1, max_length=5)


class ContinueChatResponse(BaseModel):
    route: str = "/chat"
    context: Dict[str, Any]
