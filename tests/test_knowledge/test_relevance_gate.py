"""知识库相关性门控与 RRF 归一化测试

不依赖真实 Milvus：绕过 __init__，注入假的 milvus_client / embedding_model / entity_index。
"""
import threading

import numpy as np
import pytest

from mediZJ.knowledge import milvus_kb as kb_mod
from mediZJ.knowledge.milvus_kb import MedicalKnowledgeBase, _cosine_relevance


def _make_hit(doc_id: str, distance: float, vector, text: str = "内容"):
    return {
        "id": doc_id,
        "distance": distance,
        "entity": {
            "doc_id": doc_id,
            "doc_type": "clinical_guideline",
            "text": text,
            "dense_vector": vector,
        },
    }


class _FakeClient:
    def __init__(self, hits):
        self._hits = hits

    def hybrid_search(self, **kwargs):
        return [self._hits]


class _FakeEmbedding:
    def __init__(self, query_vector):
        self._qv = np.asarray(query_vector, dtype=float)

    def encode(self, texts, normalize_embeddings=True):
        return np.array([self._qv])


def _make_kb(hits, query_vector):
    kb = object.__new__(MedicalKnowledgeBase)
    kb._client_lock = threading.RLock()
    kb.collection_name = "medical_knowledge_v2"
    kb.milvus_client = _FakeClient(hits)
    kb.embedding_model = _FakeEmbedding(query_vector)
    kb.entity_index = type("EI", (), {"search": lambda self, q: {}})()
    # Step 7 的完整文档还原：直连返回空，保留 chunk 内容
    kb.get_document_chunks = lambda doc_id: []
    return kb


QV = [1.0, 0.0]
RELEVANT = [0.9, np.sqrt(1 - 0.81)]      # cos ≈ 0.90
IRRELEVANT = [0.54, np.sqrt(1 - 0.54**2)]  # cos ≈ 0.54


class TestCosineRelevance:
    def test_dot_product_of_normalized_vectors(self):
        assert _cosine_relevance(QV, RELEVANT) == pytest.approx(0.9)

    def test_none_vector_returns_none(self):
        assert _cosine_relevance(QV, None) is None
        assert _cosine_relevance(None, RELEVANT) is None

    def test_bad_vector_returns_none(self):
        assert _cosine_relevance(QV, "not-a-vector") is None


class TestRRFNormalization:
    def test_top1_score_is_not_always_one(self):
        """归一化因子固定，top1 不再恒为 1.0"""
        hits = [
            _make_hit("d1", 0.016393, RELEVANT),
            _make_hit("d2", 0.016129, RELEVANT),
        ]
        docs = _make_kb(hits, QV).search("q", top_k=2)
        assert docs[0]["score"] < 1.0
        # 0.016393 / (2/61) ≈ 0.5
        assert docs[0]["score"] == pytest.approx(0.5, abs=0.01)

    def test_ranking_preserved(self):
        hits = [
            _make_hit("low", 0.010, RELEVANT),
            _make_hit("high", 0.030, RELEVANT),
        ]
        docs = _make_kb(hits, QV).search("q", top_k=2)
        assert [d["metadata"]["doc_id"] for d in docs] == ["high", "low"]


class TestRelevanceGate:
    def test_irrelevant_doc_filtered_out(self):
        hits = [_make_hit("rheumatoid", 0.0164, IRRELEVANT)]
        docs = _make_kb(hits, QV).search("发热吃什么退烧药", top_k=1)
        assert docs == []

    def test_relevant_doc_kept_with_relevance_field(self):
        hits = [_make_hit("hypertension", 0.0164, RELEVANT)]
        docs = _make_kb(hits, QV).search("高血压诊疗指南", top_k=1)
        assert len(docs) == 1
        assert docs[0]["relevance"] == pytest.approx(0.9, abs=0.001)

    def test_threshold_boundary_is_inclusive(self):
        vec = [0.65, np.sqrt(1 - 0.65**2)]
        hits = [_make_hit("edge", 0.0164, vec)]
        docs = _make_kb(hits, QV).search("q", top_k=1, min_relevance=0.65)
        assert len(docs) == 1

    def test_zero_threshold_disables_gate(self):
        hits = [_make_hit("rheumatoid", 0.0164, IRRELEVANT)]
        docs = _make_kb(hits, QV).search("q", top_k=1, min_relevance=0.0)
        assert len(docs) == 1

    def test_missing_vector_passes_through(self):
        """拿不到向量时放行，保证检索不因缺少相关度而整体失效"""
        hit = _make_hit("no_vec", 0.0164, None)
        docs = _make_kb([hit], QV).search("q", top_k=1)
        assert len(docs) == 1
        assert docs[0]["relevance"] is None

    def test_default_threshold_from_env(self, monkeypatch):
        monkeypatch.setattr(kb_mod, "_DEFAULT_MIN_RELEVANCE", 0.95)
        hits = [_make_hit("d1", 0.0164, RELEVANT)]  # cos 0.90 < 0.95
        assert _make_kb(hits, QV).search("q", top_k=1) == []
