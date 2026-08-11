from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.schemas import (Action, BehaviorType, BatchDetectionRequest,
                         Explanation, SingleDetectionRequest)


def _request(**overrides):
    value = {
        "user_id": "anon-user",
        "prod_id": "product-1",
        "rating": 4.0,
        "date": datetime.now(timezone.utc),
        "text": "A review",
    }
    value.update(overrides)
    return value


def test_request_rejects_unknown_fields_and_future_history():
    with pytest.raises(ValidationError):
        SingleDetectionRequest(**_request(risk_source="real"))
    with pytest.raises(ValidationError):
        SingleDetectionRequest(**_request(behavior_history=[{
            "date": datetime.now(timezone.utc) + timedelta(days=1),
            "prod_id": "product-1",
            "rating": 5.0,
            "text": "past event",
        }]))


def test_batch_review_ids_are_unique():
    item = _request(review_id="r1")
    with pytest.raises(ValidationError):
        BatchDetectionRequest(items=[item, item])


def test_unavailable_behavior_requires_insufficient_evidence():
    base = {
        "schema_version": "explanation.v2",
        "final": {"authenticity": "real", "confidence": 0.9, "fake_probability": 0.1, "threshold": 0.5, "risk_source": "real", "action": "keep"},
        "semantic": {"authenticity_scores": {"real": 0.8, "fake": 0.2}, "scores": {"real": 0.7, "misleading": 0.1, "exaggerated": 0.1, "advertising": 0.1}, "selected_type": "real"},
        "behavior": {"normality_scores": {"normal": 0.5, "abnormal": 0.5}, "scores": {"normal": 0.0, "review_manipulation": 0.0, "crowdturfing": 0.0, "bot_like": 0.0, "insufficient_evidence": 1.0}, "selected_type": "insufficient_evidence", "available": False, "history_length": 0},
        "fusion": {"semantic_weight": 1.0, "behavior_weight": 0.0, "weight_summary": "semantic dominant"},
        "evidence": {"semantic_evidence_state": "available", "behavior_evidence_state": "insufficient", "calibration_state": "uncalibrated"},
        "limitations": ["gate", "relative", "proxy", "assist"],
    }
    assert Explanation(**base).behavior.selected_type == BehaviorType.insufficient_evidence
    base["behavior"]["selected_type"] = "normal"
    with pytest.raises(ValidationError):
        Explanation(**base)
