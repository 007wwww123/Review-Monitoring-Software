from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from uuid import UUID, uuid4

from app.ml.adapter import ModelAdapter, PredictionResult
from app.models import DetectionResult, DetectionTask, ModelVersion, ReviewEvent
from app.repositories.detection import DetectionRepository
from app.schemas.detection import (
    DetectionResultSummary,
    DetectionSubmitResponse,
    SingleDetectionRequest,
    SingleDetectionResponse,
    TaskStatusResponse,
)


SEMANTIC_LABELS = ("real", "misleading", "exaggerated", "advertising")
TASK_STATUS = {
    "queued": "pending",
    "running": "running",
    "success": "succeeded",
    "partial": "succeeded",
    "failed": "failed",
    "cancelled": "cancelled",
}


class DetectionService:
    def __init__(self, db, adapter: ModelAdapter | None = None):
        self.db = db
        self.repo = DetectionRepository(db)
        self.adapter = adapter or ModelAdapter()

    @staticmethod
    def _task_response(task: DetectionTask) -> DetectionSubmitResponse:
        return DetectionSubmitResponse(
            task_id=UUID(task.task_no),
            status=TASK_STATUS[task.status],
            created_at=task.created_at,
        )

    @staticmethod
    def _review(request: SingleDetectionRequest) -> ReviewEvent:
        return ReviewEvent(
            source_type="online",
            external_review_id=request.review_id,
            user_key=sha256(request.user_id.encode("utf-8")).hexdigest(),
            product_key=request.prod_id,
            rating=request.rating,
            review_date=request.date.date(),
            review_text=request.text,
            text_sha256=sha256(request.text.encode("utf-8")).hexdigest(),
        )

    @staticmethod
    def _semantic_storage_label(prediction: PredictionResult) -> str:
        if prediction.semantic_type in SEMANTIC_LABELS:
            return prediction.semantic_type
        return max(prediction.semantic_scores, key=prediction.semantic_scores.get)

    @staticmethod
    def _risk_level(prediction: PredictionResult) -> str:
        if prediction.action == "block":
            return "high"
        if prediction.action == "review":
            return "medium"
        if prediction.action == "keep":
            return "low"
        return "unknown"

    @staticmethod
    def _explanation(prediction: PredictionResult) -> dict:
        return {
            "schema_version": "explanation.v1",
            "final": {
                "authenticity": prediction.authenticity,
                "confidence": prediction.confidence,
                "risk_source": prediction.risk_source,
                "action": prediction.action,
            },
            "semantic": {
                "scores": prediction.semantic_scores,
                "selected_type": prediction.semantic_type,
            },
            "behavior": {
                "scores": prediction.behavior_scores,
                "selected_type": prediction.behavior_type,
                "available": prediction.behavior_available,
                "history_length": min(prediction.history_length, 30),
                "is_proxy_task": True,
            },
            "fusion": {
                "semantic_weight": prediction.semantic_weight,
                "behavior_weight": prediction.behavior_weight,
                "weight_summary": prediction.weight_summary,
            },
            "evidence": {
                "semantic_evidence_state": "available",
                "behavior_evidence_state": "available" if prediction.behavior_available else "insufficient",
                "calibration_state": "uncalibrated",
            },
            "disclaimers": prediction.disclaimers,
        }

    def _result(
        self,
        task: DetectionTask,
        model: ModelVersion,
        review: ReviewEvent,
        request: SingleDetectionRequest,
        prediction: PredictionResult,
    ) -> DetectionResult:
        authenticity_probability = prediction.authenticity_scores[prediction.authenticity]
        return DetectionResult(
            task=task,
            review_event_id=review.id,
            model_version=model,
            authenticity_label=prediction.authenticity,
            authenticity_probability=authenticity_probability,
            semantic_label=self._semantic_storage_label(prediction),
            semantic_scores=prediction.semantic_scores,
            behavior_label=prediction.behavior_type,
            behavior_scores=prediction.behavior_scores,
            behavior_available=prediction.behavior_available,
            risk_level=self._risk_level(prediction),
            risk_source={"value": prediction.risk_source},
            recommendation=prediction.action,
            explanation=self._explanation(prediction),
        )

    @staticmethod
    def _summary(result: DetectionResult, model: ModelVersion, request: SingleDetectionRequest, prediction: PredictionResult) -> DetectionResultSummary:
        return DetectionResultSummary(
            result_id=result.id,
            review_id=request.review_id,
            authenticity=prediction.authenticity,
            confidence=prediction.confidence,
            semantic_type=prediction.semantic_type,
            behavior_type=prediction.behavior_type,
            risk_source=prediction.risk_source,
            action=prediction.action,
            model_version=model.version,
        )

    def submit_single(self, request: SingleDetectionRequest) -> SingleDetectionResponse:
        model = self.repo.active_model()
        if model is None:
            raise RuntimeError("no active model version is configured")
        task = DetectionTask(
            task_no=str(uuid4()),
            task_type="single",
            model_version=model,
            total_count=1,
            status="running",
            started_at=datetime.utcnow(),
        )
        try:
            self.repo.add_task(task)
            prediction = self.adapter.predict(request)
            review = self.repo.add_review(self._review(request))
            result = self.repo.add_result(self._result(task, model, review, request, prediction))
            task.success_count = 1
            task.status = "success"
            task.finished_at = datetime.utcnow()
            self.db.commit()
            return SingleDetectionResponse(
                task=self._task_response(task),
                result=self._summary(result, model, request, prediction),
            )
        except Exception:
            self.db.rollback()
            raise

    def submit_batch(self, requests: list[SingleDetectionRequest]) -> DetectionSubmitResponse:
        if not requests:
            raise ValueError("batch cannot be empty")
        model = self.repo.active_model()
        if model is None:
            raise RuntimeError("no active model version is configured")
        task = DetectionTask(
            task_no=str(uuid4()),
            task_type="batch",
            model_version=model,
            total_count=len(requests),
            status="running",
            started_at=datetime.utcnow(),
        )
        self.repo.add_task(task)
        failures: list[str] = []
        for index, request in enumerate(requests):
            try:
                with self.db.begin_nested():
                    prediction = self.adapter.predict(request)
                    review = self.repo.add_review(self._review(request))
                    self.repo.add_result(self._result(task, model, review, request, prediction))
                    task.success_count += 1
            except Exception as exc:
                failures.append(f"item {index}: {exc}")
                task.failed_count += 1
        task.status = "success" if not failures else ("partial" if task.success_count else "failed")
        task.error_message = "; ".join(failures)[:1000] if failures else None
        task.finished_at = datetime.utcnow()
        self.db.commit()
        return self._task_response(task)

    def status(self, task_no: str) -> TaskStatusResponse | None:
        task = self.repo.task_by_no(task_no)
        if task is None:
            return None
        return TaskStatusResponse(
            task_id=UUID(task.task_no),
            status=TASK_STATUS[task.status],
            total_count=task.total_count,
            completed_count=task.success_count,
            failed_count=task.failed_count,
            error_summary=task.error_message,
            created_at=task.created_at,
            started_at=task.started_at,
            finished_at=task.finished_at,
        )
