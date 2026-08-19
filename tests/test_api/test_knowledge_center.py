"""Consumer knowledge-center API tests."""

import pytest
from fastapi.testclient import TestClient

import mediZJ.api.auth as auth_module
import mediZJ.api.services.knowledge_service as knowledge_service
from mediZJ.api.auth import AuthService
from mediZJ.api.main import app
from mediZJ.api.models.knowledge import KnowledgeItem
from mediZJ.api.routers.knowledge import _search_windows
from mediZJ.api.routers.tasks import get_task_service
from mediZJ.api.services.knowledge_service import KnowledgeUnavailableError
from mediZJ.api.services.task_service import TaskService
from mediZJ.memory.session_db import SessionDB


@pytest.fixture
def knowledge_client(tmp_path, monkeypatch):
    SessionDB.reset()
    db = SessionDB(str(tmp_path / "knowledge-center.db"))
    monkeypatch.setattr(auth_module, "_auth_service", AuthService(db))
    tasks = TaskService(db)
    app.dependency_overrides[get_task_service] = lambda: tasks
    _search_windows.clear()
    with TestClient(app) as client:
        client.post("/api/auth/login", json={"username": "knowledge-user"})
        yield client, db, tasks
    app.dependency_overrides.clear()
    _search_windows.clear()
    SessionDB.reset()


def test_search_is_deduplicated_and_persisted_without_full_document(
    knowledge_client, monkeypatch
):
    client, _, tasks = knowledge_client
    items = [
        KnowledgeItem(
            id="1",
            content="A" * 500,
            metadata={"doc_id": "doc-1", "source": "指南 A", "filename": "高血压指南"},
            score=0.91,
        ),
        KnowledgeItem(
            id="2",
            content="duplicate",
            metadata={"doc_id": "doc-1", "source": "指南 A"},
            score=0.8,
        ),
    ]
    monkeypatch.setattr(knowledge_service, "search_knowledge", lambda *args, **kwargs: items)

    response = client.post(
        "/api/knowledge/search",
        json={"query": "高血压生活方式", "top_k": 5, "filter_type": "lifestyle"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["search_id"] == body["task_id"]

    user = auth_module._auth_service.db.get_or_create_user("knowledge-user")
    task = tasks.get(body["task_id"], user["user_id"])
    assert task.result["sources"][0]["doc_id"] == "doc-1"
    assert len(task.result["sources"][0]["snippet"]) == 240
    assert "A" * 500 not in str(task.result)


def test_continue_chat_rejects_forged_reference(knowledge_client, monkeypatch):
    client, _, _ = knowledge_client
    monkeypatch.setattr(
        knowledge_service,
        "search_knowledge",
        lambda *args, **kwargs: [
            KnowledgeItem(
                id="1",
                content="内容",
                metadata={"doc_id": "real-doc", "source": "真实来源"},
                score=0.9,
            )
        ],
    )
    search_id = client.post(
        "/api/knowledge/search", json={"query": "血压"}
    ).json()["search_id"]

    valid = client.post(
        f"/api/knowledge/searches/{search_id}/continue-chat",
        json={"document_ids": ["real-doc"]},
    )
    assert valid.status_code == 200
    assert valid.json()["context"]["citations"][0]["doc_id"] == "real-doc"

    forged = client.post(
        f"/api/knowledge/searches/{search_id}/continue-chat",
        json={"document_ids": ["forged-doc"]},
    )
    assert forged.status_code == 404


def test_consumer_cannot_list_or_mutate_documents(knowledge_client):
    client, _, _ = knowledge_client
    assert client.get("/api/knowledge/documents").status_code == 403
    assert client.delete("/api/knowledge/documents/doc-1").status_code == 403


def test_consumer_categories_use_plain_language(knowledge_client):
    client, _, _ = knowledge_client
    response = client.get("/api/knowledge/categories")
    assert response.status_code == 200
    categories = response.json()["types"]
    assert [item["label"] for item in categories] == [
        "疾病与症状",
        "检查指标",
        "生活方式",
        "临床指南",
    ]
    assert all(item["label"] != "疾病编码" for item in categories)


def test_search_validation_limits_query_and_top_k(knowledge_client):
    client, _, _ = knowledge_client
    assert client.post("/api/knowledge/search", json={"query": ""}).status_code == 422
    assert client.post(
        "/api/knowledge/search", json={"query": "血压", "top_k": 99}
    ).status_code == 422


def test_search_backend_failure_returns_explicit_503(knowledge_client, monkeypatch):
    client, _, _ = knowledge_client

    def unavailable(*_args, **_kwargs):
        raise KnowledgeUnavailableError("知识库暂时不可用，请稍后重试")

    monkeypatch.setattr(knowledge_service, "search_knowledge", unavailable)
    response = client.post("/api/knowledge/search", json={"query": "血压"})
    assert response.status_code == 503
    assert "暂时不可用" in response.json()["detail"]
