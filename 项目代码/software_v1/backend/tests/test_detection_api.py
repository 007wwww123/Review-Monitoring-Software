from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session

from app.api import routes
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import ModelVersion, SysUser
from app.security import hash_password
from app.services.detection import DetectionService
from app.ml.adapter import PredictionResult


class FakeAdapter:
    def predict(self, request):
        return PredictionResult(
            authenticity="real",
            authenticity_scores={"real": 0.9, "fake": 0.1},
            confidence=0.8,
            semantic_scores={"real": 0.8, "misleading": 0.1, "exaggerated": 0.05, "advertising": 0.05},
            semantic_type="real",
            behavior_scores={"normal": 0.0, "review_manipulation": 0.0, "crowdturfing": 0.0, "bot_like": 0.0, "insufficient_evidence": 1.0},
            behavior_type="insufficient_evidence",
            behavior_available=False,
            history_length=0,
            semantic_weight=1.0,
            behavior_weight=0.0,
            weight_summary="semantic dominant",
            risk_source="real",
            action="keep",
            route="run_fusion",
            reason="mandatory_semantic_behavior_fusion",
        )


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-only-secret-with-sufficient-length")
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = Session(engine)
    db.add(ModelVersion(
        version="v1.0.0",
        model_name="albert-gru-fusion",
        checkpoint_path="/controlled/cascade_fusion_best.pt",
        checkpoint_sha256="a" * 64,
        tokenizer_name="local-albert",
        config_json={},
        dataset_manifest_json={},
        is_active=True,
    ))
    db.add(SysUser(username="reviewer", password_hash=hash_password("test-password"), role="reviewer", status="active"))
    db.commit()
    service = DetectionService(db, FakeAdapter())
    monkeypatch.setattr(routes, "DetectionService", lambda current_db: service)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def payload(review_id: str, text: str = "A review"):
    return {
        "review_id": review_id,
        "user_id": "user-1",
        "prod_id": "product-1",
        "rating": 4.0,
        "date": datetime(2026, 8, 1, tzinfo=timezone.utc).isoformat(),
        "text": text,
    }


def auth_headers(client):
    response = client.post("/api/v1/auth/login", json={"username": "reviewer", "password": "test-password"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_single_detection_route_returns_result_and_task(client):
    response = client.post("/api/v1/detections", json=payload("r1"))
    assert response.status_code == 202
    body = response.json()
    assert body["task"]["status"] == "succeeded"
    assert body["result"]["behavior_type"] == "insufficient_evidence"

    status = client.get(f"/api/v1/detections/{body['task']['task_id']}")
    assert status.status_code == 200
    assert status.json()["completed_count"] == 1


def test_batch_detection_route_returns_one_task(client):
    response = client.post(
        "/api/v1/detections/batch",
        json={"items": [payload("r1"), payload("r2", "Second review")]},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "succeeded"
    status = client.get(f"/api/v1/detections/{body['task_id']}")
    assert status.json()["total_count"] == 2
    assert status.json()["completed_count"] == 2


def test_authenticated_result_detail_returns_typed_explanation(client):
    submitted = client.post("/api/v1/detections/single", json=payload("detail-1")).json()
    result_id = submitted["result"]["result_id"]
    response = client.get(f"/api/v1/results/{result_id}", headers=auth_headers(client))
    assert response.status_code == 200
    body = response.json()
    assert body["result_id"] == result_id
    assert body["task_id"] == submitted["task"]["task_id"]
    assert body["explanation"]["behavior"]["selected_type"] == "insufficient_evidence"
    assert len(body["explanation"]["disclaimers"]) == 4


def test_result_detail_requires_authentication_and_returns_404(client):
    assert client.get("/api/v1/results/999999").status_code == 401
    response = client.get("/api/v1/results/999999", headers=auth_headers(client))
    assert response.status_code == 404
    assert response.json()["detail"] == "result not found"


def test_task_report_creation_and_downloads(client):
    submitted = client.post("/api/v1/detections/single", json=payload("report-1")).json()
    headers = auth_headers(client)
    created = client.post("/api/v1/reports", json={"task_id": submitted["task"]["task_id"]}, headers=headers)
    assert created.status_code == 200
    report_id = created.json()["report_id"]
    assert isinstance(report_id, int)
    json_download = client.get(f"/api/v1/reports/{report_id}/download?format=json", headers=headers)
    csv_download = client.get(f"/api/v1/reports/{report_id}/download?format=csv", headers=headers)
    assert json_download.status_code == 200
    assert json_download.json()["total_count"] == 1
    assert csv_download.status_code == 200
    assert csv_download.headers["content-type"].startswith("text/csv")
    assert "metric,value" in csv_download.text
