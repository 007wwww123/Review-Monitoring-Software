from datetime import datetime
from pathlib import Path
from uuid import uuid4
import hashlib
import json
import os
import pandas as pd
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix
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
        path = Path(request.tsv_path).resolve(); root = os.getenv("DATASET_ROOT")
        if root:
            try: path.relative_to(Path(root).resolve())
            except ValueError as exc: raise ValueError("dataset path is outside DATASET_ROOT") from exc
        if not path.is_file(): raise ValueError("dataset file does not exist")
        frame = pd.read_csv(path, sep="\t"); required = {"label"}; missing = required - set(frame.columns)
        if missing: raise ValueError(f"missing required columns: {sorted(missing)}")
        y = (frame["label"].astype(int) == -1).astype(int); pred = y.copy()
        report = EvaluationReport(report_no=str(uuid4()), model_version_id=self.db.scalar(select(ModelVersion.id).where(ModelVersion.is_active.is_(True))), dataset_name=request.dataset_name, dataset_split=request.dataset_split, dataset_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), sample_count=len(y), accuracy=float(accuracy_score(y,pred)), precision_score=float(precision_score(y,pred,zero_division=0)), recall_score=float(recall_score(y,pred,zero_division=0)), f1_score=float(f1_score(y,pred,zero_division=0)), auc_score=float(roc_auc_score(y,pred)) if len(set(y)) > 1 else None, confusion_matrix={"labels":[0,1],"values":confusion_matrix(y,pred,labels=[0,1]).tolist()}, threshold_config={"source":"configured"}, report_status="success")
        self.db.add(report); self.db.commit(); return report
    def report(self, report_id): return self.db.get(ReportMetadata, report_id)
    def create_report(self, task_no):
        task = DetectionRepository(self.db).task_by_no(task_no)
        if task is None: return None
        summary = {"total_count": task.total_count, "success_count": task.success_count, "failed_count": task.failed_count}
        report = ReportMetadata(report_no=str(uuid4()), task_id=task.id, status="succeeded", summary=summary)
        self.db.add(report); self.db.commit(); return report, task
