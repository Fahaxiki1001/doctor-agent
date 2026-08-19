"""Report upload, confirmation, interpretation and privacy tests."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import mediZJ.api.auth as auth_module
from mediZJ.api.auth import AuthService
from mediZJ.api.main import app
from mediZJ.api.models.report import (
    ReportAnalysisDraft,
    ReportMeasurement,
)
from mediZJ.api.routers.reports import get_report_service
from mediZJ.api.services.image_analyzer import ImageAnalyzer
from mediZJ.api.services.image_upload_service import ImageUploadService
from mediZJ.api.services.report_service import ReportService
from mediZJ.api.services.task_service import TaskService
from mediZJ.memory.session_db import SessionDB


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"test-report-content"


class FakeAnalyzer:
    async def analyze_report(self, image_paths):
        return ReportAnalysisDraft(
            document_type="lab_report",
            confidence=0.93,
            measurements=[
                ReportMeasurement(
                    name="空腹血糖",
                    value="7.2",
                    unit="mmol/L",
                    reference_range="3.9-6.1",
                    abnormal_flag="high",
                    confidence=0.95,
                    raw_text="空腹血糖 7.2 mmol/L 3.9-6.1",
                ),
                ReportMeasurement(
                    name="白细胞",
                    value="无法辨认",
                    unit="10^9/L",
                    reference_range="3.5-9.5",
                    confidence=0.61,
                    raw_text="白细胞 ...",
                ),
            ],
        )


class EmptyAnalyzer:
    async def analyze_report(self, image_paths):
        return ReportAnalysisDraft(
            document_type="lab_report",
            confidence=0.2,
            measurements=[],
            warnings=["图片过于模糊"],
            manual_review=True,
        )


class FailingAnalyzer:
    async def analyze_report(self, image_paths):
        raise RuntimeError("vision unavailable")


@pytest.fixture
def report_client(tmp_path, monkeypatch):
    SessionDB.reset()
    db = SessionDB(str(tmp_path / "reports.db"))
    monkeypatch.setattr(auth_module, "_auth_service", AuthService(db))
    uploads = ImageUploadService(db, tmp_path / "uploads")
    service = ReportService(
        db=db,
        task_service=TaskService(db),
        upload_service=uploads,
        analyzer=FakeAnalyzer(),
        knowledge_search=lambda *args, **kwargs: [],
    )
    app.dependency_overrides[get_report_service] = lambda: service
    with TestClient(app) as client:
        client.post("/api/auth/login", json={"username": "report-user"})
        yield client, db, uploads
    app.dependency_overrides.clear()
    SessionDB.reset()


def _upload(client: TestClient) -> dict:
    response = client.post(
        "/api/reports",
        files={"file": ("lab.png", PNG_BYTES, "image/png")},
        data={"document_type": "lab_report"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_confirmed_only_report_lifecycle(report_client):
    client, db, _ = report_client
    uploaded = _upload(client)
    report_id = uploaded["report_id"]
    analyzed = client.post(f"/api/reports/{report_id}/analyze")
    assert analyzed.status_code == 200
    draft = analyzed.json()
    assert draft["status"] == "waiting_confirmation"
    assert len(draft["measurements"]) == 2

    first, second = draft["measurements"]
    confirmed = client.put(
        f"/api/reports/{report_id}/measurements/confirm",
        json={
            "measurements": [
                {
                    "measurement_id": first["measurement_id"],
                    "name": first["name"],
                    "value": "5.0",
                    "unit": first["unit"],
                    "reference_range": "3.9-6.1",
                    "user_confirmed": True,
                },
                {
                    "measurement_id": second["measurement_id"],
                    "name": second["name"],
                    "unable_to_confirm": True,
                },
            ]
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    body = confirmed.json()
    assert body["status"] == "completed"
    assert len(body["result"]["confirmed_measurements"]) == 1
    assert body["result"]["confirmed_measurements"][0]["value"] == "5.0"
    assert body["result"]["confirmed_measurements"][0]["abnormal_flag"] == "normal"
    assert "无法辨认" not in str(body["result"])

    task = db.get_health_task(body["task"]["task_id"])
    assert "无法辨认" not in task["result"]


def test_invalid_confirmed_value_is_rejected(report_client):
    client, _, _ = report_client
    report_id = _upload(client)["report_id"]
    draft = client.post(f"/api/reports/{report_id}/analyze").json()
    item = draft["measurements"][0]
    response = client.put(
        f"/api/reports/{report_id}/measurements/confirm",
        json={
            "measurements": [
                {
                    "measurement_id": item["measurement_id"],
                    "name": item["name"],
                    "value": "drop table",
                    "user_confirmed": True,
                }
            ]
        },
    )
    assert response.status_code == 409


def test_delete_cascades_private_file_and_rows(report_client):
    client, db, uploads = report_client
    uploaded = _upload(client)
    report_id = uploaded["report_id"]
    filename = Path(uploaded["image_url"]).name
    assert (uploads.upload_dir / filename).exists()

    response = client.delete(f"/api/reports/{report_id}")
    assert response.json() == {"deleted": True}
    assert not (uploads.upload_dir / filename).exists()
    assert db.get_upload(filename) is None
    assert db.get_report(report_id) is None
    assert db.get_health_task(uploaded["task"]["task_id"]) is None


def test_report_is_private_and_response_has_no_server_path(report_client):
    client, _, uploads = report_client
    uploaded = _upload(client)
    assert str(uploads.upload_dir) not in str(uploaded)
    assert "base64" not in str(uploaded).lower()

    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"username": "other-report-user"})
    assert client.get(f"/api/reports/{uploaded['report_id']}").status_code == 404
    assert client.delete(f"/api/reports/{uploaded['report_id']}").status_code == 404


def test_extension_magic_mismatch_is_rejected(report_client):
    client, _, _ = report_client
    response = client.post(
        "/api/reports",
        files={"file": ("fake.jpg", PNG_BYTES, "image/jpeg")},
    )
    assert response.status_code == 400
    assert "扩展名" in response.json()["detail"]


def test_expired_report_image_is_cleaned(report_client):
    client, db, uploads = report_client
    uploaded = _upload(client)
    filename = Path(uploaded["image_url"]).name
    expired = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    db._execute(
        lambda conn: conn.execute(
            "UPDATE uploads SET expires_at = ? WHERE filename = ?",
            (expired, filename),
        )
    )

    assert uploads.cleanup_expired() == 1
    assert db.get_upload(filename) is None
    assert not (uploads.upload_dir / filename).exists()


def test_stale_report_processing_recovers_to_retryable_failure(report_client):
    client, db, uploads = report_client
    uploaded = _upload(client)
    report_id = uploaded["report_id"]
    task_id = uploaded["task"]["task_id"]
    report_row = db.get_report(report_id)
    user_id = report_row["user_id"]
    tasks = TaskService(db)
    tasks.update(task_id, user_id, status="processing")
    db.update_report(report_id, user_id, {"status": "analyzing"})
    service = ReportService(
        db=db,
        task_service=tasks,
        upload_service=uploads,
        analyzer=FakeAnalyzer(),
        knowledge_search=lambda *args, **kwargs: [],
    )

    assert service.recover_stale() == 1
    recovered = service.get(report_id, user_id)
    assert recovered.status.value == "failed"
    assert recovered.task.status.value == "failed"
    assert "重试" in (recovered.error or "")


def test_cancel_report_stops_task_and_removes_private_image(report_client):
    client, db, uploads = report_client
    uploaded = _upload(client)
    filename = Path(uploaded["image_url"]).name

    response = client.post(f"/api/reports/{uploaded['report_id']}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["task"]["status"] == "cancelled"
    assert db.get_upload(filename) is None
    assert not (uploads.upload_dir / filename).exists()


def test_report_confidence_threshold_is_configurable(monkeypatch):
    monkeypatch.setenv("REPORT_VISION_MIN_CONFIDENCE", "0.85")
    analyzer = ImageAnalyzer()
    assert analyzer.report_min_confidence == 0.85

    monkeypatch.setenv("REPORT_VISION_MIN_CONFIDENCE", "1.5")
    with pytest.raises(ValueError, match="0 到 1"):
        ImageAnalyzer()


def test_no_measurements_fails_without_fabricated_values(report_client):
    client, _, _ = report_client
    service = app.dependency_overrides[get_report_service]()
    service.analyzer = EmptyAnalyzer()
    uploaded = _upload(client)

    response = client.post(f"/api/reports/{uploaded['report_id']}/analyze")
    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["measurements"] == []
    assert "未识别到" in response.json()["error"]


def test_vision_failure_is_retryable(report_client):
    client, _, _ = report_client
    service = app.dependency_overrides[get_report_service]()
    service.analyzer = FailingAnalyzer()
    uploaded = _upload(client)

    failed = client.post(f"/api/reports/{uploaded['report_id']}/analyze")
    assert failed.json()["status"] == "failed"
    assert "分析失败" in failed.json()["error"]

    service.analyzer = FakeAnalyzer()
    retried = client.post(f"/api/reports/{uploaded['report_id']}/retry")
    assert retried.status_code == 200
    assert retried.json()["status"] == "waiting_confirmation"


@pytest.mark.asyncio
async def test_image_analyzer_parses_multi_page_structured_drafts(monkeypatch):
    monkeypatch.setenv("VISION_API_KEY", "test-key")
    monkeypatch.setenv("VISION_BASE_URL", "https://vision.invalid/v1")
    monkeypatch.setenv("REPORT_VISION_MIN_CONFIDENCE", "0.8")
    analyzer = ImageAnalyzer()

    class VisionClient:
        calls = 0

        async def chat(self, _messages):
            self.calls += 1
            return json.dumps(
                {
                    "document_type": "lab_report",
                    "confidence": 0.9 if self.calls == 1 else 0.75,
                    "warnings": [],
                    "manual_review": False,
                    "measurements": [
                        {
                            "name": f"指标{self.calls}",
                            "value": str(self.calls),
                            "unit": "mmol/L",
                            "reference_range": "0-2",
                            "confidence": 0.9,
                        }
                    ],
                },
                ensure_ascii=False,
            )

    monkeypatch.setattr(analyzer, "_get_client", lambda: VisionClient())
    monkeypatch.setattr(analyzer, "_image_to_base64", lambda _path: "data:image/png;base64,AA==")

    draft = await analyzer.analyze_report(["page-1.png", "page-2.png"])
    assert len(draft.measurements) == 2
    assert draft.confidence == 0.75
    assert draft.manual_review is True


@pytest.mark.asyncio
async def test_image_analyzer_invalid_json_requires_manual_review(monkeypatch):
    monkeypatch.setenv("VISION_API_KEY", "test-key")
    monkeypatch.setenv("VISION_BASE_URL", "https://vision.invalid/v1")
    analyzer = ImageAnalyzer()

    class InvalidVisionClient:
        async def chat(self, _messages):
            return "not-json"

    monkeypatch.setattr(analyzer, "_get_client", lambda: InvalidVisionClient())
    monkeypatch.setattr(analyzer, "_image_to_base64", lambda _path: "data:image/png;base64,AA==")

    draft = await analyzer.analyze_report(["page.png"])
    assert draft.manual_review is True
    assert draft.measurements == []
    assert "结构化提取失败" in draft.warnings[0]
