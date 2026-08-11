from datetime import datetime
from hashlib import sha256
from uuid import uuid4

from app.ml.adapter import ModelAdapter
from app.models import DetectionTask, ReviewEvent
from app.repositories.detection import DetectionRepository
from app.schemas.detection import DetectionSubmitResponse, SingleDetectionRequest, TaskStatusResponse


class DetectionService:
    def __init__(self, db, adapter: ModelAdapter | None = None):
        self.db = db
        self.repo = DetectionRepository(db)
        self.adapter = adapter or ModelAdapter()

    def submit_single(self, request: SingleDetectionRequest) -> DetectionSubmitResponse:
        model = self.repo.active_model()
        if model is None:
            raise RuntimeError("no active model version is configured")
        prediction = self.adapter.predict(request)
        now = datetime.utcnow()
        review = ReviewEvent(source_type="online", external_review_id=request.review_id,
            user_key=sha256(request.user_id.encode()).hexdigest(), product_key=request.prod_id,
            rating=request.rating, review_date=request.date.date(), review_text=request.text,
            text_sha256=sha256(request.text.encode()).hexdigest())
        self.repo.add_review(review)
        task = self.repo.add_task(DetectionTask(task_no=str(uuid4()), task_type="single",
            model_version=model, total_count=1, success_count=1, status="success",
            started_at=now, finished_at=now))
        self.db.commit()
        return DetectionSubmitResponse(task_id=uuid4(), status="succeeded", created_at=now)

    def status(self, task_no: str) -> TaskStatusResponse | None:
        task = self.repo.task_by_no(task_no)
        if task is None:
            return None
        return TaskStatusResponse(task_id=uuid4(), status={"queued":"pending", "running":"running", "success":"succeeded", "partial":"succeeded", "failed":"failed", "cancelled":"cancelled"}[task.status], total_count=task.total_count, completed_count=task.success_count, failed_count=task.failed_count, error_summary=task.error_message, created_at=task.created_at, started_at=task.started_at, finished_at=task.finished_at)
