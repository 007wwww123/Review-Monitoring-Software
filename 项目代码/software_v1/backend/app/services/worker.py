"""Database-backed single-GPU worker for queued batch detections."""

from datetime import datetime, timezone

from app.ml.adapter import ModelAdapter
from app.repositories.detection import DetectionRepository
from app.schemas.detection import SingleDetectionRequest
from app.services.detection import DetectionService


class BatchDetectionWorker:
    def __init__(self, db, adapter: ModelAdapter):
        self.db = db
        self.adapter = adapter
        self.repo = DetectionRepository(db)

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    def run_once(self) -> bool:
        task = self.repo.next_queued_batch()
        if task is None:
            self.db.rollback()
            return False
        if task.model_version is None:
            task.status = "failed"
            task.error_message = "task has no immutable model version"
            task.finished_at = self._utcnow()
            self.db.commit()
            return True

        task.status = "running"
        task.started_at = self._utcnow()
        self.db.commit()
        service = DetectionService(self.db, self.adapter)
        failures: list[str] = []
        for item in task.items:
            item.status = "running"
            item.started_at = self._utcnow()
            self.db.commit()
            try:
                request = SingleDetectionRequest.model_validate(item.request_json)
                with self.db.begin_nested():
                    result, _ = service._process_item(task, task.model_version, request)
                    item.result = result
                    item.status = "succeeded"
                    task.success_count += 1
            except Exception as exc:
                item.status = "failed"
                item.error_message = str(exc)[:1000]
                task.failed_count += 1
                failures.append(f"item {item.item_index}: {exc}")
            item.finished_at = self._utcnow()
            self.db.commit()

        task.status = "success" if not failures else ("partial" if task.success_count else "failed")
        task.error_message = "; ".join(failures)[:1000] if failures else None
        task.finished_at = self._utcnow()
        self.db.commit()
        return True
