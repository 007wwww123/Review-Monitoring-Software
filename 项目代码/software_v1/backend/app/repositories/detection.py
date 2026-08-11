from sqlalchemy import func, select
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

    def results(self, task_no: str | None = None, result_id: int | None = None, page: int = 1, page_size: int = 20):
        query = select(DetectionResult).join(DetectionTask)
        count = select(func.count(DetectionResult.id)).join(DetectionTask)
        if task_no:
            query = query.where(DetectionTask.task_no == task_no); count = count.where(DetectionTask.task_no == task_no)
        if result_id is not None:
            query = query.where(DetectionResult.id == result_id); count = count.where(DetectionResult.id == result_id)
        return self.db.scalars(query.order_by(DetectionResult.id.desc()).offset((page - 1) * page_size).limit(page_size)).all(), self.db.scalar(count) or 0
