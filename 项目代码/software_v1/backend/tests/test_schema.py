import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import DetectionResult, DetectionTask, ModelVersion, ReviewEvent, SysUser


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


def test_only_seven_core_tables_are_declared():
    names = set(Base.metadata.tables)
    assert names == {"sys_user", "review_event", "detection_task", "detection_result", "model_version", "evaluation_report", "operation_log", "explanation_snapshot", "report_metadata"}


def test_review_and_result_can_be_traced_to_model(session):
    user = SysUser(username="reviewer", password_hash="argon2-hash")
    model = ModelVersion(version="v1.0.0", model_name="albert-gru-fusion", checkpoint_path="/controlled/model.pt", checkpoint_sha256="a" * 64, tokenizer_name="albert/albert-base-v2", config_json={}, dataset_manifest_json={})
    review = ReviewEvent(source_type="online", review_text="sample", text_sha256="b" * 64)
    task = DetectionTask(task_no="task-1", task_type="single", creator=user, model_version=model)
    result = DetectionResult(task=task, review_event_id=1, model_version=model, authenticity_label="fake", authenticity_probability=0.9, semantic_label="real", behavior_label="insufficient_evidence", behavior_available=False, risk_level="unknown")
    session.add_all([user, model, review])
    session.flush()
    result.review_event_id = review.id
    session.add(result)
    session.commit()
    assert result.task.model_version.version == "v1.0.0"


def test_probability_range_constraint(session):
    model = ModelVersion(version="v1", model_name="m", checkpoint_path="/m", checkpoint_sha256="a" * 64, tokenizer_name="t", config_json={}, dataset_manifest_json={})
    review = ReviewEvent(source_type="online", review_text="sample", text_sha256="b" * 64)
    task = DetectionTask(task_no="task-2", task_type="single", model_version=model)
    session.add_all([model, review, task])
    session.flush()
    session.add(DetectionResult(task_id=task.id, review_event_id=review.id, model_version_id=model.id, authenticity_label="fake", authenticity_probability=1.5, semantic_label="real", behavior_label="insufficient_evidence", behavior_available=False, risk_level="unknown"))
    with pytest.raises(IntegrityError):
        session.commit()
