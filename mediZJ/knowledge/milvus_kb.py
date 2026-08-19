"""
医学知识库（Milvus）— 三路混合检索（Milvus 2.5+ 内置中文 BM25 Function 优化版）

检索路径：
  Path 1 — 稠密向量 : bge-small-zh-v1.5 → Milvus IP ANN
  Path 2 — 内置 BM25 稀疏 : 原始文本字符串流 → Milvus 内置结巴分词与标准 BM25 评分
  Path 3 — 医学实体精确匹配 : jieba + 内存倒排索引

融合策略：Milvus RRF (Path1+2) + App-level Entity Boost (Path3)

兼容性：search() 签名与返回值结构保持不变，所有 Skill 无需改动
"""
import json
import math
import os
import threading
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import List, Dict, Any, Optional

import numpy as np
from loguru import logger

from pymilvus import (
    MilvusClient, DataType,
    AnnSearchRequest, RRFRanker,
    Function, FunctionType,
)
from mediZJ.knowledge.entity_index import MedicalEntityIndex
from mediZJ.memory.embedding import load_embedding_model

COLLECTION_NAME = "medical_knowledge_v2"

# 语义相关性门控阈值（余弦相似度）。低于该值的召回视为不相关，直接不返回，
# 避免库内没有对应文档时把最相近的无关文档当成证据引用。
# 实测标定（bge-small-zh-v1.5，clinical_guideline）：命中 0.81~0.84，未命中 0.49~0.59。
# 设为 0 可关闭门控，回退到改动前行为。
_DEFAULT_MIN_RELEVANCE = float(os.getenv("KB_MIN_RELEVANCE", "0.65"))


def _cosine_relevance(query_vector, doc_vector) -> Optional[float]:
    """query 与文档向量的余弦相似度（两侧均已 L2 归一化，点积即余弦）

    拿不到向量时返回 None —— 上层视为放行，保证检索不因缺少相关度而整体失效。
    """
    if doc_vector is None or query_vector is None:
        return None
    try:
        return float(np.dot(np.asarray(query_vector), np.asarray(doc_vector)))
    except (TypeError, ValueError) as e:
        logger.warning(f"Relevance computation failed: {e}")
        return None


def _serialized(func):
    """串行化 Milvus 客户端调用（pymilvus 对本地文件型客户端无线程安全保证）"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        with self._client_lock:
            return func(self, *args, **kwargs)
    return wrapper


# ---- Trace 集成（可选）----
try:
    from trace import traced_span, SpanType, ToolAttributes as TraceToolAttrs
    _TRACE_AVAILABLE = True
except ImportError:
    _TRACE_AVAILABLE = False
    traced_span = None  # type: ignore
    SpanType = None  # type: ignore
    TraceToolAttrs = None  # type: ignore


@contextmanager
def _noop_ctx():
    yield None


class MedicalKnowledgeBase:
    """医学知识库（单例）"""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        db_path: str = None,
        collection_name: str = COLLECTION_NAME,
        embedding_model: str = "BAAI/bge-small-zh-v1.5",
    ):
        if db_path is None:
            import os
            db_path = os.path.join(os.path.dirname(__file__), "data", "milvus_lite.db")
        if hasattr(self, "_initialized"):
            return

        self.db_path = db_path
        self.collection_name = collection_name

        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # ---- Embedding 模型（进程内共享缓存实例） ----
        self.embedding_model = load_embedding_model(embedding_model)
        self.embedding_dim = self.embedding_model.get_sentence_embedding_dimension()
        logger.info(f"Embedding model loaded (dimension={self.embedding_dim})")

        # ---- Milvus Client ----
        # pymilvus 客户端调用串行化锁（需在 _create_collection 前初始化）
        self._client_lock = threading.RLock()
        logger.info(f"Connecting to Milvus Lite: {db_path}")
        self.milvus_client = MilvusClient(db_path)

        # ---- 创建 Collection ----
        if not self.milvus_client.has_collection(collection_name):
            logger.info(f"Creating collection: {collection_name}")
            self._create_collection()

        # ---- Entity Index ----
        self.entity_index = MedicalEntityIndex()
        self._build_entity_index()

        self._initialized = True

    # ------------------------------------------------------------------
    # Schema 创建 (Milvus内置端到端全文检索方案)
    # ------------------------------------------------------------------

    def _create_collection(self):
        """创建内置中文分词与 BM25 Function 的显式 Schema"""
        schema = MilvusClient.create_schema(
            auto_id=True, enable_dynamic_field=True,
        )

        schema.add_field("id", DataType.INT64, is_primary=True, auto_id=True)
        schema.add_field("doc_id", DataType.VARCHAR, max_length=256)
        schema.add_field("doc_type", DataType.VARCHAR, max_length=64)
        schema.add_field("chunk_id", DataType.INT64)
        schema.add_field("total_chunks", DataType.INT64)

        # 为原始文本添加内置中文 Jieba 分析器
        schema.add_field(
            "text", DataType.VARCHAR, max_length=65535,
            analyzer_params={"type": "chinese"}
        )

        schema.add_field("dense_vector", DataType.FLOAT_VECTOR, dim=self.embedding_dim)
        schema.add_field("sparse_vector", DataType.SPARSE_FLOAT_VECTOR)

        # 声明内置 BM25 Function
        # 数据落盘时，Milvus 会自动调用此 Function 将 text 离线分词并转化为稀疏向量进行存储
        bm25_fn = Function(
            name="text_bm25_emb",
            function_type=FunctionType.BM25,
            input_field_names=["text"],
            output_field_names=["sparse_vector"]
        )
        schema.add_function(bm25_fn)

        index_params = self.milvus_client.prepare_index_params()
        index_params.add_index("dense_vector", index_type="FLAT", metric_type="IP")

        # 将 metric_type 改为标准的 BM25 评分机制
        index_params.add_index(
            "sparse_vector", index_type="SPARSE_INVERTED_INDEX", metric_type="BM25",
        )

        self.milvus_client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
            index_params=index_params,
        )
        logger.info("Collection created successfully with native Chinese BM25 Function.")

    def _build_entity_index(self):
        """从当前 collection 的文档文本构建实体倒排索引"""
        try:
            rows = self.milvus_client.query(
                collection_name=self.collection_name,
                filter="id >= 0",
                output_fields=["doc_id", "text"],
                limit=16384,
            )
        except Exception as e:
            logger.warning(f"Failed to query docs for entity index: {e}")
            return

        if not rows:
            return

        # 按 doc_id 聚合所有 chunk 文本（避免仅取 chunk_0 遗漏关键实体）
        docs_by_id: dict = {}
        for row in rows:
            doc_id = row.get("doc_id", "")
            text = row.get("text", "")
            if doc_id and text:
                if doc_id not in docs_by_id:
                    docs_by_id[doc_id] = text
                else:
                    docs_by_id[doc_id] += "\n" + text

        docs = [{"doc_id": k, "text": v} for k, v in docs_by_id.items()]

        self.entity_index.build_from_kb(docs)

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 1024, overlap: int = 100) -> List[str]:
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start = end - overlap
        return chunks

    # ------------------------------------------------------------------
    # 文档 CRUD
    # ------------------------------------------------------------------

    @_serialized
    def add_documents(
        self, documents: List[Dict[str, Any]], chunk_size: int = 1024,
    ) -> int:
        """
        添加文档到知识库（分块 + 稠密向量化 + 插入）。
        内置 BM25 稀疏向量无需传入，会在 Milvus 端自动生成。
        """
        if not documents:
            logger.warning("No documents to add")
            return 0

        logger.info(
            f"Adding {len(documents)} documents to knowledge base "
            f"(chunk_size={chunk_size})..."
        )

        # 分块
        all_chunks = []
        for doc in documents:
            chunks = self._chunk_text(doc["content"], chunk_size=chunk_size)
            meta = doc.get("metadata", {})
            for i, chunk in enumerate(chunks):
                all_chunks.append({
                    "doc_id": doc["id"],
                    "doc_type": meta.get("type", ""),
                    "chunk_id": i,
                    "total_chunks": len(chunks),
                    "text": chunk,
                    "disease": meta.get("disease", ""),
                    "source": meta.get("source", ""),
                    "filename": meta.get("filename", ""),
                    "content_hash": meta.get("content_hash", ""),
                    "version": meta.get("version", ""),
                    "published_at": meta.get("published_at", ""),
                    "reviewed_at": meta.get("reviewed_at", ""),
                    "applicable_population": meta.get("applicable_population", ""),
                })

        logger.info(f"Split into {len(all_chunks)} chunks")

        # 仅在客户端生称密向量
        texts = [c["text"] for c in all_chunks]
        vectors = self.embedding_model.encode(texts, show_progress_bar=True)

        # 组装插入数据
        data = []
        for i, chunk in enumerate(all_chunks):
            entry: Dict[str, Any] = {
                "doc_id": chunk["doc_id"],
                "doc_type": chunk["doc_type"],
                "chunk_id": chunk["chunk_id"],
                "total_chunks": chunk["total_chunks"],
                "text": chunk["text"],
                "dense_vector": vectors[i].tolist(),
                # 在此完全不需要显式传入 sparse_vector，Milvus 引擎会自动计算并填充
                "disease": chunk["disease"],
                "source": chunk["source"],
                "filename": chunk["filename"],
                "content_hash": chunk["content_hash"],
                "version": chunk["version"],
                "published_at": chunk["published_at"],
                "reviewed_at": chunk["reviewed_at"],
                "applicable_population": chunk["applicable_population"],
            }
            data.append(entry)

        self.milvus_client.insert(self.collection_name, data)
        logger.info(f"Successfully added {len(data)} chunks")

        # 完全删除了原来庞大的库内 query 全量拉取并 fit/save 离线 pkl 的代码，彻底根治延迟高/崩溃隐患

        # 增量更新实体索引
        seen_doc_ids: set = set()
        for chunk in all_chunks:
            doc_id = chunk["doc_id"]
            if doc_id not in seen_doc_ids:
                seen_doc_ids.add(doc_id)
                self.entity_index.add_document(doc_id, chunk["text"])

        return len(data)

    # ------------------------------------------------------------------
    # 三路混合检索
    # ------------------------------------------------------------------

    def _hybrid_search(
        self,
        query: str,
        top_k: int,
        filter_expr: Optional[str],
    ) -> tuple:
        """Path 1+2: Dense + BM25 混合检索（Milvus RRF）

        Returns:
            (hits, query_vector)。query_vector 供上层计算语义相关度（余弦）。
        """
        query_vector = self.embedding_model.encode(
            [query], normalize_embeddings=True,
        )[0]

        dense_req = AnnSearchRequest(
            data=[query_vector.tolist()],
            anns_field="dense_vector",
            param={"metric_type": "IP", "params": {"nprobe": 16}},
            limit=top_k * 3,
            expr=filter_expr,
        )

        # 不再调用客户端编码，直接传中文原始文本字符串
        sparse_req = AnnSearchRequest(
            data=[query],  # 传入原始文本，Milvus 在服务端对其执行 chinese analyzer 分词并利用索引完成检索评分
            anns_field="sparse_vector",
            param={"metric_type": "BM25"},  # 指明评分度量为标准的 BM25 算法
            limit=top_k * 3,
            expr=filter_expr,
        )

        results = self.milvus_client.hybrid_search(
            collection_name=self.collection_name,
            reqs=[dense_req, sparse_req],
            ranker=RRFRanker(k=60),
            limit=top_k * 3,
            output_fields=[
                "id", "doc_id", "doc_type", "chunk_id",
                "total_chunks", "text", "dense_vector",
            ],
        )

        if not results or len(results) == 0:
            return [], query_vector

        # 安全加固：在第一优先级进行异常值过滤与防护
        for hit in results[0]:
            dist = hit.get("distance", 0.0)
            if math.isnan(dist) or math.isinf(dist) or dist < 0:
                hit["distance"] = 0.0
        return results[0], query_vector

    @_serialized
    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_type: Optional[str] = None,
        min_relevance: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        三路混合检索。

        Args:
            query: 查询文本
            top_k: 返回 Top-K 个去重文档
            filter_type: 可选文档类型过滤
            min_relevance: 语义相关性下限（余弦），缺省取 KB_MIN_RELEVANCE（0.65）。
                低于该值的召回会被丢弃——库内没有对应文档时宁可返回空，
                也不要把最相近的无关文档当作证据。

        Returns:
            文档列表，每个文档含 ``id``, ``content``, ``metadata``, ``score``（RRF 融合分，
            仅用于排序）, ``relevance``（余弦相似度，用于判断是否真的相关）
        """
        threshold = (
            _DEFAULT_MIN_RELEVANCE if min_relevance is None else min_relevance
        )
        logger.debug(
            f"Hybrid search: query={query[:80]} top_k={top_k} "
            f"filter_type={filter_type} min_relevance={threshold}"
        )

        _ctx = traced_span(SpanType.TOOL, name="knowledge_search") if _TRACE_AVAILABLE else _noop_ctx()
        with _ctx as t:
            if t and TraceToolAttrs:
                t.tool_attrs = TraceToolAttrs(
                    tool_name="knowledge_search",
                    arguments={"query": query[:200], "top_k": top_k, "filter_type": filter_type},
                )

            # Step 1: 实体加权（Path 3）
            entity_boost = self.entity_index.search(query)

            # Step 2: Dense + BM25 混合检索（Path 1+2）
            filter_expr = (
                f'doc_type == "{filter_type}"' if filter_type else None
            )
            try:
                hits, query_vector = self._hybrid_search(query, top_k, filter_expr)
            except Exception as e:
                logger.error(f"Hybrid search failed: {e}")
                if t:
                    t.tool_attrs.result_summary = json.dumps({"error": str(e)}, ensure_ascii=False)
                return []

            # Step 3: RRF 线性动态映射 + Entity Boost 融合
            ENTITY_BONUS_COEFFICIENT = 0.15
            RRF_K = 60

            # 归一化因子固定为两路检索均排第一时的 RRF 理论上界。
            # 不能用「本次结果集内的最高分」——那会让 top1 恒为 1.0，与真实相关度无关。
            normalization_factor = 2.0 / (RRF_K + 1)

            scoring_detail = []
            for hit in hits:
                doc_id = hit.get("entity", {}).get("doc_id", "")
                hit["_doc_id"] = doc_id
                hit["_text"] = hit.get("entity", {}).get("text", "")
                hit["_relevance"] = _cosine_relevance(
                    query_vector, hit.get("entity", {}).get("dense_vector")
                )

                raw_rrf = hit.get("distance", 0.0)
                # 进行比例归一化缩放
                normalized_rrf = raw_rrf / normalization_factor if normalization_factor > 0 else raw_rrf
                bonus = entity_boost.get(doc_id, 0.0) * ENTITY_BONUS_COEFFICIENT

                # 融合最终得分
                hit["final_score"] = min(normalized_rrf + bonus, 1.0)
                scoring_detail.append({
                    "doc_id": doc_id,
                    "raw_rrf": round(raw_rrf, 6),
                    "normalized_rrf": round(normalized_rrf, 4),
                    "entity_bonus": round(bonus, 4),
                    "final_score": round(hit["final_score"], 4),
                    "relevance": (
                        round(hit["_relevance"], 4)
                        if hit["_relevance"] is not None else None
                    ),
                })

            # Step 4: 按 final_score 重排
            hits.sort(key=lambda h: h["final_score"], reverse=True)

            # Step 5: 按 doc_id 去重，保留最高 final_score
            seen_docs: Dict[str, Dict[str, Any]] = {}
            for hit in hits:
                doc_id = hit["_doc_id"]
                if not doc_id:
                    doc_id = str(hit.get("id", ""))
                score = hit["final_score"]
                if doc_id not in seen_docs or score > seen_docs[doc_id]["score"]:
                    seen_docs[doc_id] = {
                        "id": hit.get("id"),
                        "content": hit["_text"],
                        "metadata": {
                            "doc_id": doc_id,
                            "type": hit.get("entity", {}).get("doc_type", ""),
                        },
                        "score": round(score, 4),
                        "relevance": (
                            round(hit["_relevance"], 4)
                            if hit.get("_relevance") is not None else None
                        ),
                    }

            # Step 6: 按分数排序，取 top_k
            top_docs = sorted(
                seen_docs.values(), key=lambda d: d["score"], reverse=True,
            )[:top_k]

            # Step 6.5: 语义相关性门控——宁可返回空，也不要把无关文档当成证据
            if threshold > 0:
                kept = []
                for doc in top_docs:
                    rel = doc.get("relevance")
                    if rel is None:
                        logger.warning(
                            f"Relevance unavailable for {doc['metadata'].get('doc_id')}, "
                            "passing through without gating"
                        )
                        kept.append(doc)
                    elif rel >= threshold:
                        kept.append(doc)
                    else:
                        logger.debug(
                            f"Filtered irrelevant doc {doc['metadata'].get('doc_id')} "
                            f"(relevance={rel} < {threshold})"
                        )
                filtered_count = len(top_docs) - len(kept)
                top_docs = kept
            else:
                filtered_count = 0

            # Step 7: 还原完整文档内容（拼接所有 chunk），补充完整 metadata
            for doc in top_docs:
                doc_id = doc["metadata"].get("doc_id", "")
                if doc_id:
                    full_chunks = self.get_document_chunks(doc_id)
                    if full_chunks:
                        doc["content"] = "\n".join(
                            c["content"] for c in full_chunks
                        )
                        if full_chunks:
                            first_meta = full_chunks[0].get("metadata", {})
                            doc["metadata"] = first_meta

            # 回填 trace 监控指标
            if t:
                t.tool_attrs.result_summary = json.dumps({
                    "paths": ["dense_vector(IP)", "native_bm25_sparse", "entity_exact_match"],
                    "rrf_k": RRF_K,
                    "entity_bonus_coefficient": ENTITY_BONUS_COEFFICIENT,
                    "entity_boost_matches": len(entity_boost),
                    "raw_candidates": len(hits),
                    "scoring_top5": scoring_detail[:5],
                    "min_relevance": threshold,
                    "filtered_by_relevance": filtered_count,
                    "final_count": len(top_docs),
                    "top_score": top_docs[0]["score"] if top_docs else 0,
                    "top_relevance": top_docs[0].get("relevance") if top_docs else None,
                }, ensure_ascii=False)
                t.tool_attrs.success = len(top_docs) > 0

            logger.debug(f"Found {len(top_docs)} unique documents")
            return top_docs

    # ------------------------------------------------------------------
    # Collection 管理
    # ------------------------------------------------------------------

    @_serialized
    def delete_collection(self):
        """删除并重建 collection（用于重建）"""
        if self.milvus_client.has_collection(self.collection_name):
            self.milvus_client.drop_collection(self.collection_name)
            logger.info(f"Deleted collection: {self.collection_name}")
        self._create_collection()

    @_serialized
    def count_documents(self) -> int:
        """统计去重后的文档数量"""
        try:
            return len(self.list_documents())
        except Exception as e:
            logger.warning(f"Failed to count documents: {e}")
            return 0

    @_serialized
    def list_documents(self) -> List[Dict[str, Any]]:
        """列出知识库中所有去重后的文档摘要"""
        try:
            all_rows = self.milvus_client.query(
                collection_name=self.collection_name,
                filter="id >= 0",
                output_fields=["doc_id", "doc_type", "disease", "source",
                               "filename", "chunk_id", "version", "published_at",
                               "reviewed_at", "applicable_population"],
                limit=16384,
            )
        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            return []

        docs: Dict[str, Dict[str, Any]] = {}
        for row in all_rows:
            doc_id = row.get("doc_id", "unknown")
            if doc_id not in docs:
                docs[doc_id] = {
                    "doc_id": doc_id,
                    "filename": row.get("filename", ""),
                    "type": row.get("doc_type", ""),
                    "disease": row.get("disease", ""),
                    "source": row.get("source", ""),
                    "version": row.get("version") or None,
                    "published_at": row.get("published_at") or None,
                    "reviewed_at": row.get("reviewed_at") or None,
                    "applicable_population": row.get("applicable_population") or None,
                    "chunk_ids": set(),
                }
            chunk_id = row.get("chunk_id")
            if chunk_id is not None:
                docs[doc_id]["chunk_ids"].add(chunk_id)

        result = []
        for doc in docs.values():
            doc["chunk_count"] = len(doc["chunk_ids"])
            del doc["chunk_ids"]
            result.append(doc)

        return result

    @_serialized
    def document_exists_by_hash(self, content_hash: str) -> bool:
        """根据内容 hash 检查文档是否已存在"""
        filter_expr = f'content_hash == "{content_hash}"'
        try:
            rows = self.milvus_client.query(
                collection_name=self.collection_name,
                filter=filter_expr,
                output_fields=["doc_id"],
                limit=1,
            )
            return len(rows) > 0
        except Exception:
            return False

    @_serialized
    def get_document_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
        """获取指定文档的所有 chunk，按 chunk_id 排序"""
        filter_expr = f'doc_id == "{doc_id}"'
        try:
            rows = self.milvus_client.query(
                collection_name=self.collection_name,
                filter=filter_expr,
                output_fields=[
                    "id", "chunk_id", "total_chunks", "text",
                    "doc_type", "disease", "source", "filename",
                    "content_hash", "version", "published_at", "reviewed_at",
                    "applicable_population",
                ],
                limit=16384,
            )
        except Exception as e:
            logger.error(f"Failed to get chunks for {doc_id}: {e}")
            return []

        chunks = []
        seen_chunk_ids: set = set()
        for row in rows:
            chunk_id = row.get("chunk_id", 0)
            if chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(chunk_id)
            chunks.append({
                "milvus_id": row["id"],
                "chunk_id": chunk_id,
                "content": row.get("text", ""),
                "total_chunks": row.get("total_chunks", 0),
                "metadata": {
                    "doc_id": doc_id,
                    "type": row.get("doc_type", ""),
                    "disease": row.get("disease", ""),
                    "source": row.get("source", ""),
                    "filename": row.get("filename", ""),
                    "content_hash": row.get("content_hash", ""),
                    "version": row.get("version") or None,
                    "published_at": row.get("published_at") or None,
                    "reviewed_at": row.get("reviewed_at") or None,
                    "applicable_population": row.get("applicable_population") or None,
                    "chunk_id": chunk_id,
                    "total_chunks": row.get("total_chunks", 0),
                },
            })

        chunks.sort(key=lambda c: c["chunk_id"])
        return chunks

    @_serialized
    def delete_document(self, doc_id: str) -> int:
        """删除指定文档的所有 chunk，返回删除数量"""
        chunks = self.get_document_chunks(doc_id)
        if not chunks:
            return 0

        filter_expr = f'doc_id == "{doc_id}"'
        try:
            self.milvus_client.delete(
                collection_name=self.collection_name,
                filter=filter_expr,
            )
            logger.info(f"Deleted {len(chunks)} chunks for doc_id={doc_id}")
        except Exception as e:
            logger.error(f"Failed to delete document {doc_id}: {e}")
            return 0

        # 同步更新实体索引
        self.entity_index.remove_document(doc_id)
        return len(chunks)

    @_serialized
    def update_document(
        self,
        doc_id: str,
        content: str,
        metadata: Dict[str, Any],
        chunk_size: int = 1024,
    ) -> int:
        """更新文档：删除旧 chunk，重新分块插入"""
        self.delete_document(doc_id)
        doc = {"id": doc_id, "content": content, "metadata": metadata}
        return self.add_documents([doc], chunk_size=chunk_size)
