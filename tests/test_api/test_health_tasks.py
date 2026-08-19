"""Unified health-task lifecycle and API tests."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

import mediZJ.api.auth as auth_module
import mediZJ.api.routers.tasks as tasks_router
from mediZJ.api.auth import AuthService
from mediZJ.api.main import app
from mediZJ.api.models.task import (
    HealthTaskCreate,
    InvalidTaskTransition,
    TaskStatus,
    TaskType,
)
from mediZJ.api.routers.tasks import get_task_service
from mediZJ.api.services.task_service import TaskService
from mediZJ.memory.session_db import SessionDB


@pytest.fixture
def task_db(tmp_path):
    SessionDB.reset()
    db = SessionDB(str(tmp_path / "tasks.db"))
    yield db
    app.dependency_overrides.clear()
    SessionDB.reset()


def test_status_transition_and_atomic_conflict(task_db):
    user = task_db.get_or_create_user("task-user")
    service = TaskService(task_db)
    task = service.create(
        user["user_id"],
        HealthTaskCreate(task_type=TaskType.TRIAGE),
    )

    collecting = service.update(
        task.task_id, user["user_id"], status=TaskStatus.COLLECTING
    )
    assert collecting.status == TaskStatus.COLLECTING

    with pytest.raises(InvalidTaskTransition):
        service.update(task.task_id, user["user_id"], status=TaskStatus.COMPLETED)


def test_schema_initialization_is_idempotent(task_db):
    task_db._execute(task_db._create_tables)
    task_db._execute(task_db._migrate_tables)
    columns = task_db._execute(
        lambda conn: conn.execute("PRAGMA table_info(health_tasks)").fetchall()
    )
    assert {column["name"] for column in columns} >= {
        "task_id",
        "user_id",
        "task_type",
        "status",
        "result",
        "safety_flags",
    }


def test_task_api_isolates_users(task_db, monkeypatch):
    service = TaskService(task_db)
    monkeypatch.setattr(auth_module, "_auth_service", AuthService(task_db))
    app.dependency_overrides[get_task_service] = lambda: service

    with TestClient(app) as alice:
        alice.post("/api/auth/login", json={"username": "alice-task"})
        created = alice.post("/api/tasks", json={"task_type": "triage"})
        assert created.status_code == 201
        task_id = created.json()["task_id"]

        alice.post("/api/auth/logout")
        alice.post("/api/auth/login", json={"username": "bob-task"})
        assert alice.get(f"/api/tasks/{task_id}").status_code == 404
        assert alice.post(f"/api/tasks/{task_id}/cancel").status_code == 404
        assert alice.delete(f"/api/tasks/{task_id}").status_code == 404

        alice.post("/api/auth/logout")
        alice.post("/api/auth/login", json={"username": "alice-task"})
        assert alice.post(f"/api/tasks/{task_id}/cancel").status_code == 200
        assert alice.delete(f"/api/tasks/{task_id}").json() == {"deleted": True}

    connection = sqlite3.connect(task_db.db_path)
    try:
        audit = connection.execute(
            "SELECT task_hash, user_hash, action FROM health_task_audit"
        ).fetchone()
    finally:
        connection.close()
    assert audit is not None
    assert task_id not in audit
    assert audit[2] == "deleted"


def test_task_feedback_is_owned_and_contains_no_health_snapshot(task_db, monkeypatch):
    service = TaskService(task_db)
    monkeypatch.setattr(auth_module, "_auth_service", AuthService(task_db))
    app.dependency_overrides[get_task_service] = lambda: service

    with TestClient(app) as client:
        client.post("/api/auth/login", json={"username": "feedback-owner"})
        created = client.post(
            "/api/tasks",
            json={
                "task_type": "triage",
                "input_snapshot": {"symptom": "private symptom text"},
            },
        ).json()
        task_id = created["task_id"]
        response = client.post(
            f"/api/tasks/{task_id}/feedback",
            json={"rating": "dislike", "reason_codes": ["unclear"], "comment": ""},
        )
        assert response.status_code == 200

        client.post("/api/auth/logout")
        client.post("/api/auth/login", json={"username": "feedback-other"})
        assert (
            client.post(
                f"/api/tasks/{task_id}/feedback",
                json={"rating": "like"},
            ).status_code
            == 404
        )

    row = task_db._execute(
        lambda conn: conn.execute(
            "SELECT * FROM health_task_feedback WHERE task_id = ?", (task_id,)
        ).fetchone()
    )
    assert row["rating"] == "dislike"
    assert "private symptom text" not in str(dict(row))


def test_health_feedback_sends_only_deidentified_signal(task_db, monkeypatch):
    service = TaskService(task_db)
    monkeypatch.setattr(auth_module, "_auth_service", AuthService(task_db))
    captured = {}

    class FakeEvolution:
        def submit_health_task_feedback(self, **payload):
            captured.update(payload)
            return {"signal_id": "signal"}

    monkeypatch.setattr(tasks_router, "EvolutionService", lambda: FakeEvolution())
    app.dependency_overrides[get_task_service] = lambda: service

    with TestClient(app) as client:
        client.post("/api/auth/login", json={"username": "signal-owner"})
        created = client.post(
            "/api/tasks",
            json={
                "task_type": "report_interpretation",
                "input_snapshot": {"report_text": "private lab value 7.2"},
            },
        ).json()
        response = client.post(
            f"/api/tasks/{created['task_id']}/feedback",
            json={
                "rating": "dislike",
                "reason_codes": ["unsafe", "not-allowed"],
                "comment": "private lab value 7.2 and my name",
            },
        )
        assert response.status_code == 200

    assert captured == {
        "task_type": "report_interpretation",
        "task_status": "created",
        "rating": "dislike",
        "reason_codes": ["unsafe", "not-allowed"],
        "safety_decision": "",
    }


def test_health_task_metrics_cover_operational_rates(task_db):
    user = task_db.get_or_create_user("metrics-user")
    service = TaskService(task_db)

    triage = service.create(
        user["user_id"], HealthTaskCreate(task_type=TaskType.TRIAGE)
    )
    service.cancel(triage.task_id, user["user_id"])

    knowledge = service.create(
        user["user_id"], HealthTaskCreate(task_type=TaskType.KNOWLEDGE_SEARCH)
    )
    service.update(knowledge.task_id, user["user_id"], status=TaskStatus.PROCESSING)
    service.update(
        knowledge.task_id,
        user["user_id"],
        status=TaskStatus.COMPLETED,
        result={"total": 0},
    )

    report_task = service.create(
        user["user_id"],
        HealthTaskCreate(task_type=TaskType.REPORT_INTERPRETATION),
    )
    service.update(report_task.task_id, user["user_id"], status=TaskStatus.PROCESSING)
    service.update(report_task.task_id, user["user_id"], status=TaskStatus.COMPLETED)
    task_db.save_upload(
        "metrics.png",
        user["user_id"],
        "metrics.png",
        "image/png",
        10,
        purpose="report",
    )
    task_db.create_report(
        {
            "report_id": "metrics-report",
            "task_id": report_task.task_id,
            "user_id": user["user_id"],
            "upload_filename": "metrics.png",
            "document_type": "lab_report",
            "status": "completed",
        }
    )

    metrics = task_db.get_health_task_metrics(user["user_id"])
    assert metrics["total"] == 3
    assert metrics["completion_rate"] == pytest.approx(2 / 3)
    assert metrics["questionnaire_abandonment_rate"] == 1
    assert metrics["knowledge_empty_rate"] == 1
    assert metrics["report_confirmation_rate"] == 1
