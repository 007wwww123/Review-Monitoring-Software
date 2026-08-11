from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.ml.adapter import PredictionResult
from app.models import DetectionResult, DetectionTask, ModelVersion
from app.schemas.detection import SingleDetectionRequest
from app.services.detection import DetectionService
from app.services.worker import BatchDetectionWorker


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


def request(text: str, review_id: str, when: datetime | None = None) -> SingleDetectionRequest:
    return SingleDetectionRequest(
        review_id=review_id,
        user_id="user-1",
        prod_id="product-1",
        rating=4.0,
        date=when or datetime(2026, 8, 1, tzinfo=timezone.utc),
        text=text,
    )


def prediction() -> PredictionResult:
    return PredictionResult(
        authenticity="real",
        authenticity_scores={"real": 0.9, "fake": 0.1},
        threshold=0.5,
        confidence=0.8,
        semantic_authenticity_scores={"real": 0.8, "fake": 0.2},
        semantic_scores={"real": 0.8, "misleading": 0.1, "exaggerated": 0.05, "advertising": 0.05},
        semantic_type="real",
        behavior_scores={"normal": 0.0, "review_manipulation": 0.0, "crowdturfing": 0.0, "bot_like": 0.0, "insufficient_evidence": 1.0},
        behavior_normality_scores={"normal": 0.5, "abnormal": 0.5},
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


class FakeAdapter:
    def __init__(self, fail_text: str | None = None):
        self.fail_text = fail_text
        self.requests = []

    def predict(self, item):
        self.requests.append(item)
        if item.text == self.fail_text:
            raise ValueError("synthetic prediction failure")
        return prediction()


def active_model(session):
    model = ModelVersion(
        version="v1.0.0",
        model_name="albert-gru-fusion",
        checkpoint_path="/controlled/cascade_fusion_best.pt",
        checkpoint_sha256="a" * 64,
        tokenizer_name="local-albert",
        config_json={},
        dataset_manifest_json={},
        is_active=True,
    )
    session.add(model)
    session.flush()
    return model


def test_single_detection_persists_task_review_and_result(session):
    model = active_model(session)
    response = DetectionService(session, FakeAdapter()).submit_single(request("good", "r1"))

    task = session.scalar(select(DetectionTask).where(DetectionTask.task_no == str(response.task.task_id)))
    result = session.scalar(select(DetectionResult).where(DetectionResult.task_id == task.id))
    assert response.task.status == "succeeded"
    assert response.result.result_id == result.id
    assert task.model_version_id == model.id
    assert task.success_count == 1
    assert result.behavior_label == "insufficient_evidence"
    assert result.behavior_available is False
    assert result.review_event.review_time == datetime(2026, 8, 1)


def test_server_history_uses_only_prior_persisted_events(session):
    active_model(session)
    adapter = FakeAdapter()
    service = DetectionService(session, adapter)
    service.submit_single(request("first", "r1", datetime(2026, 8, 1, 9, 30, tzinfo=timezone.utc)))
    service.submit_single(request("second", "r2", datetime(2026, 8, 2, 10, 45, tzinfo=timezone.utc)))
    history = adapter.requests[-1].behavior_history
    assert [item.review_id for item in history] == ["r1"]
    assert history[0].date < adapter.requests[-1].date


def test_batch_detection_is_queued_then_worker_keeps_partial_successes(session):
    active_model(session)
    response = DetectionService(session, FakeAdapter("bad")).submit_batch(
        [request("good", "r1"), request("bad", "r2"), request("good-2", "r3")]
    )

    task = session.scalar(select(DetectionTask).where(DetectionTask.task_no == str(response.task_id)))
    assert response.status == "pending"
    assert BatchDetectionWorker(session, FakeAdapter("bad")).run_once() is True
    session.refresh(task)
    results = session.scalars(select(DetectionResult).where(DetectionResult.task_id == task.id)).all()
    assert task.status == "partial"
    assert task.total_count == 3
    assert task.success_count == 2
    assert task.failed_count == 1
    assert len(results) == 2
    assert "item 1" in task.error_message
