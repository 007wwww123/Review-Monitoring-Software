from datetime import date, datetime, time
from sqlalchemy import func, or_, select
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

    def results(self, task_no: str | None = None, result_id: int | None = None, keyword: str | None = None, authenticity: str | None = None, action: str | None = None, date_from: date | None = None, date_to: date | None = None, page: int = 1, page_size: int = 20):
        # 所有筛选条件采用 AND 组合，日期按自然日闭区间处理。
        query = select(DetectionResult).join(DetectionTask)
        count = select(func.count(DetectionResult.id)).join(DetectionTask)
        if task_no:
            query = query.where(DetectionTask.task_no == task_no); count = count.where(DetectionTask.task_no == task_no)
        if result_id is not None:
            query = query.where(DetectionResult.id == result_id); count = count.where(DetectionResult.id == result_id)
        if keyword:
            # user_key 是匿名哈希标识；不在查询中暴露原始用户身份。
            value = f"%{keyword}%"
            condition = or_(ReviewEvent.external_review_id.ilike(value), ReviewEvent.user_key.ilike(value), ReviewEvent.product_key.ilike(value), ReviewEvent.review_text.ilike(value))
            query = query.join(ReviewEvent, DetectionResult.review_event_id == ReviewEvent.id).where(condition)
            count = count.join(ReviewEvent, DetectionResult.review_event_id == ReviewEvent.id).where(condition)
        if authenticity:
            query = query.where(DetectionResult.authenticity_label == authenticity); count = count.where(DetectionResult.authenticity_label == authenticity)
        if action:
            query = query.where(DetectionResult.recommendation == action); count = count.where(DetectionResult.recommendation == action)
        if date_from:
            start = datetime.combine(date_from, time.min); query = query.where(DetectionResult.created_at >= start); count = count.where(DetectionResult.created_at >= start)
        if date_to:
            # 结束日期包含当天 23:59:59.999999。
            end = datetime.combine(date_to, time.max); query = query.where(DetectionResult.created_at <= end); count = count.where(DetectionResult.created_at <= end)
        return self.db.scalars(query.order_by(DetectionResult.id.desc()).offset((page - 1) * page_size).limit(page_size)).all(), self.db.scalar(count) or 0
