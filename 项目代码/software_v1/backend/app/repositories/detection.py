from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DetectionResult, DetectionTask, ModelVersion, ReviewEvent


class DetectionRepository:
    def __init__(self, db: Session):
        self.db = db

    def active_model(self) -> ModelVersion | None:
        return self.db.scalar(select(ModelVersion).where(ModelVersion.is_active.is_(True)).order_by(ModelVersion.id.desc()))

    def add_review(self, review: ReviewEvent) -> ReviewEvent:
        self.db.add(review); self.db.flush(); return review

    def add_task(self, task: DetectionTask) -> DetectionTask:
        self.db.add(task); self.db.flush(); return task

    def add_result(self, result: DetectionResult) -> DetectionResult:
        self.db.add(result); self.db.flush(); return result

    def task_by_no(self, task_no: str) -> DetectionTask | None:
        return self.db.scalar(select(DetectionTask).where(DetectionTask.task_no == task_no))
