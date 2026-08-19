"""Symptom triage workflow tests."""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from pydantic import ValidationError

import mediZJ.api.auth as auth_module
from mediZJ.api.auth import AuthService
from mediZJ.api.main import app
from mediZJ.api.models.triage import RiskAssessment, RiskLevel, TriageCreateRequest
from mediZJ.api.routers.triage import get_triage_service
from mediZJ.api.services.task_service import TaskService
from mediZJ.api.services.triage_parser import parse_risk_assessment
from mediZJ.api.services.triage_service import TriageService
from mediZJ.api.services.triage_rules import RED_FLAG_RULES
from mediZJ.memory.session_db import SessionDB


async def _low_risk_skill(_symptoms: str):
    return {
        "risk_level": "low",
        "recommendation": "继续观察，持续或加重时就医",
    }


async def _symptom_pattern_skill(_symptoms: str):
    return {"patterns": ["症状涉及：上呼吸道"], "possible_diseases": ["不应展示"]}


@pytest.fixture
def client_and_db(tmp_path, monkeypatch):
    SessionDB.reset()
    db = SessionDB(str(tmp_path / "triage.db"))
    monkeypatch.setattr(auth_module, "_auth_service", AuthService(db))
    service = TriageService(
        TaskService(db),
        risk_skill=_low_risk_skill,
        symptom_skill=_symptom_pattern_skill,
    )
    app.dependency_overrides[get_triage_service] = lambda: service
    with TestClient(app) as client:
        client.post("/api/auth/login", json={"username": "triage-user"})
        yield client, db
    app.dependency_overrides.clear()
    SessionDB.reset()


def test_emergency_precheck_stops_normal_advice(client_and_db):
    client, _ = client_and_db
    response = client.post(
        "/api/triage/tasks", json={"symptom": "突然胸痛而且喘不上气"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["task"]["status"] == "needs_medical_attention"
    assert body["result"]["risk_level"] == "emergency"
    assert body["questionnaire"] is None
    assert all(
        "立即" in action or "120" in action for action in body["result"]["next_steps"]
    )


@pytest.mark.parametrize("rule", RED_FLAG_RULES, ids=lambda rule: rule.code)
def test_every_red_flag_rule_stops_normal_triage(client_and_db, rule):
    client, _ = client_and_db
    response = client.post(
        "/api/triage/tasks", json={"symptom": rule.terms[0]}
    )
    body = response.json()
    assert response.status_code == 201
    assert body["task"]["status"] == "needs_medical_attention"
    assert body["result"]["risk_level"] == "emergency"
    assert rule.label in body["result"]["red_flags_found"]
    assert body["task"]["trace_id"]


def test_questionnaire_to_completed_result(client_and_db):
    client, _ = client_and_db
    created = client.post("/api/triage/tasks", json={"symptom": "轻微鼻塞"}).json()
    assert created["task"]["status"] == "collecting"
    questionnaire_id = created["questionnaire"]["questionnaire_id"]

    completed = client.post(
        f"/api/triage/tasks/{created['task']['task_id']}/answer",
        json={
            "questionnaire_id": questionnaire_id,
            "answers": {
                "duration": "2天",
                "severity": "轻微",
                "age": 30,
                "red_flags": ["均无"],
            },
        },
    )
    assert completed.status_code == 200
    assert completed.json()["task"]["status"] == "completed"
    assert completed.json()["result"]["risk_level"] == "low"

    duplicate = client.post(
        f"/api/triage/tasks/{created['task']['task_id']}/answer",
        json={"questionnaire_id": questionnaire_id, "answers": {"age": 99}},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["result"]["risk_level"] == "low"


def test_expired_questionnaire_is_failed_and_traced(client_and_db):
    client, db = client_and_db
    created = client.post("/api/triage/tasks", json={"symptom": "头痛"}).json()
    task_id = created["task"]["task_id"]
    db._execute(
        lambda conn: conn.execute(
            "UPDATE health_tasks SET expires_at = ? WHERE task_id = ?",
            ((datetime.now() - timedelta(minutes=1)).isoformat(), task_id),
        )
    )
    response = client.post(
        f"/api/triage/tasks/{task_id}/answer",
        json={
            "questionnaire_id": created["questionnaire"]["questionnaire_id"],
            "answers": {"duration": "1天"},
        },
    )
    assert response.status_code == 200
    assert response.json()["task"]["status"] == "failed"
    assert response.json()["task"]["trace_id"]


def test_cross_user_triage_returns_not_found(client_and_db):
    client, _ = client_and_db
    task_id = client.post("/api/triage/tasks", json={"symptom": "头痛"}).json()["task"][
        "task_id"
    ]
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"username": "another-user"})
    assert client.get(f"/api/triage/tasks/{task_id}").status_code == 404
    assert client.delete(f"/api/triage/tasks/{task_id}").status_code == 404


def test_invalid_skill_output_falls_back_to_high_risk():
    result = parse_risk_assessment("not-json")
    assert result.risk_level == RiskLevel.HIGH
    assert result.confidence == 0


def test_legacy_skill_output_is_normalized():
    result = parse_risk_assessment(
        {"risk_level": "medium", "recommendation": "建议尽快咨询医生"}
    )
    assert result.risk_level == RiskLevel.MEDIUM
    assert result.next_steps == ["建议尽快咨询医生"]


@pytest.mark.asyncio
async def test_invalid_live_skill_output_is_conservative(tmp_path):
    SessionDB.reset()
    db = SessionDB(str(tmp_path / "invalid-skill.db"))
    user = db.get_or_create_user("skill-user")

    async def invalid_skill(_symptoms: str):
        return "not-json"

    service = TriageService(
        TaskService(db),
        risk_skill=invalid_skill,
        symptom_skill=_symptom_pattern_skill,
    )
    created = await service.create(
        user["user_id"],
        TriageCreateRequest(
            symptom="头痛",
            answers={
                "duration": "1天",
                "severity": "轻微",
                "age": 30,
                "red_flags": ["均无"],
            },
        ),
    )
    assert created.result is not None
    assert created.result.risk_level == RiskLevel.HIGH
    SessionDB.reset()


def test_emergency_assessment_requires_action():
    with pytest.raises(ValidationError):
        RiskAssessment(
            risk_level="emergency",
            urgency="立即处理",
            confidence=1,
            next_steps=[],
        )
