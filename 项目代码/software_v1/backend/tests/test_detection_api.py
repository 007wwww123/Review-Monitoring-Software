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
from app.models import ModelVersion
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
