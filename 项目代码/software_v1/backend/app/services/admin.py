from pathlib import Path
from uuid import uuid4
import hashlib
import os
import pandas as pd
from sqlalchemy import select

from app.models import EvaluationReport, ModelVersion, ReportMetadata, DetectionTask, DetectionResult
from app.repositories.detection import DetectionRepository

class AdminService:
    def __init__(self, db): self.db = db
    def models(self): return self.db.scalars(select(ModelVersion).order_by(ModelVersion.created_at.desc())).all()
    def model(self, version): return self.db.scalar(select(ModelVersion).where(ModelVersion.version == version))
    def activate(self, version):
        model = self.model(version)
        if model is None: return None
        if not Path(model.checkpoint_path).is_file(): raise ValueError("checkpoint is unavailable")
        for item in self.models(): item.is_active = item.id == model.id
        self.db.commit(); return model
    def evaluate(self, request):
        # 先校验路径、列和标签；没有可复现的真实模型时必须阻断，不能生成伪指标。
        path = Path(request.tsv_path).resolve(); root = os.getenv("DATASET_ROOT")
        if root:
            try: path.relative_to(Path(root).resolve())
            except ValueError as exc: raise ValueError("dataset path is outside DATASET_ROOT") from exc
        if not path.is_file(): raise ValueError("dataset file does not exist")
        frame = pd.read_csv(path, sep="\t"); required = {"user_id", "prod_id", "rating", "label", "date", "text"}; missing = required - set(frame.columns)
        if missing: raise ValueError(f"missing required columns: {sorted(missing)}")
        labels = set(frame["label"].astype(int))
        if not labels <= {-1, 1}: raise ValueError("label must contain only 1 and -1")
        if self.db.scalar(select(ModelVersion.id).where(ModelVersion.is_active.is_(True))) is None: raise ValueError("no active model is configured")
        raise ValueError("real model evaluation adapter is not configured for this deployment")
    def report(self, report_id): return self.db.get(ReportMetadata, report_id)
    def create_report(self, task_no):
        task = DetectionRepository(self.db).task_by_no(task_no)
        if task is None: return None
        rows = self.db.scalars(select(DetectionResult).where(DetectionResult.task_id == task.id)).all()
        def counts(values):
            output = {}
            for value in values: output[str(value)] = output.get(str(value), 0) + 1
            return output
        summary = {"total_count": task.total_count, "success_count": task.success_count, "failed_count": task.failed_count, "authenticity_distribution": counts(r.authenticity_label for r in rows), "risk_level_distribution": counts(r.risk_level for r in rows), "behavior_evidence_distribution": counts("available" if r.behavior_available else "insufficient" for r in rows), "model_version": task.model_version.version if task.model_version else None, "data_source": "real_model" if task.model_version else "unknown", "is_mock": False, "is_proxy_task": True}
        report = ReportMetadata(report_no=str(uuid4()), task_id=task.id, status="succeeded", summary=summary)
        self.db.add(report); self.db.commit(); return report, task
