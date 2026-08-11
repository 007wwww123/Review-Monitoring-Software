import importlib
import os
from pathlib import Path
from uuid import uuid4

import pandas as pd
from sqlalchemy import select

from app.ml.adapter import ModelAdapter
from app.ml.manifest import sha256_file
from app.models import (
    DetectionResult,
    EvaluationReport,
    ModelVersion,
    ReportMetadata,
)
from app.repositories.detection import DetectionRepository


class AdminService:
    def __init__(self, db, adapter: ModelAdapter | None = None):
        self.db = db
        self.adapter = adapter

    def models(self):
        return self.db.scalars(
            select(ModelVersion).order_by(ModelVersion.created_at.desc())
        ).all()

    def model(self, version):
        return self.db.scalar(
            select(ModelVersion).where(ModelVersion.version == version)
        )

    def activate(self, version):
        model = self.model(version)
        if model is None:
            return None
        raise ValueError(
            "online model switching is disabled; restart with a validated model manifest"
        )

    def evaluate(self, request, created_by: int | None = None):
        # Validate the controlled dataset before loading it into the real model.
        path = Path(request.tsv_path).resolve()
        root = os.getenv("DATASET_ROOT")
        if root:
            try:
                path.relative_to(Path(root).resolve())
            except ValueError as exc:
                raise ValueError("dataset path is outside DATASET_ROOT") from exc
        if not path.is_file():
            raise ValueError("dataset file does not exist")

        frame = pd.read_csv(path, sep="\t")
        required = {"user_id", "prod_id", "rating", "label", "date", "text"}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"missing required columns: {sorted(missing)}")
        labels = set(frame["label"].astype(int))
        if not labels <= {-1, 1}:
            raise ValueError("label must contain only 1 and -1")
        if self.adapter is None:
            raise ValueError("real ALBERT-GRU model is not loaded")

        loaded = self.adapter.loaded_model
        model_row = self.db.scalar(
            select(ModelVersion).where(
                ModelVersion.checkpoint_sha256 == loaded.checkpoint_sha256
            )
        )
        if model_row is None:
            raise ValueError("loaded model is not registered in the database")

        import torch
        from sklearn.metrics import (
            accuracy_score,
            average_precision_score,
            confusion_matrix,
            f1_score,
            precision_score,
            recall_score,
            roc_auc_score,
        )
        from torch.utils.data import DataLoader

        data_module = importlib.import_module("spam_cascade.data")
        normalized = data_module.load_reviews(path)
        builder = data_module.BehaviorFeatureBuilder(
            minimum_history=loaded.config.minimum_history,
            maximum_history=loaded.config.maximum_history,
        )
        samples = builder.build(normalized, include_unavailable=True)
        dataset = data_module.FusionReviewDataset(
            normalized,
            samples,
            loaded.tokenizer,
            loaded.config.max_length,
        )
        loader = DataLoader(
            dataset,
            batch_size=int(os.getenv("EVALUATION_BATCH_SIZE", "32")),
            shuffle=False,
            collate_fn=data_module.collate_fusion,
        )

        truth: list[int] = []
        fake_probabilities: list[float] = []
        loaded.model.eval()
        with torch.no_grad():
            for batch in loader:
                labels_batch = batch.pop("authenticity_labels")
                batch.pop("semantic_labels")
                batch.pop("behavior_binary_labels")
                batch.pop("behavior_type_labels")
                model_batch = {
                    key: value.to(loaded.device) for key, value in batch.items()
                }
                output = loaded.model(**model_batch)
                probabilities = torch.softmax(
                    output.fusion.authenticity_logits, dim=-1
                )[:, 1]
                truth.extend(labels_batch.tolist())
                fake_probabilities.extend(probabilities.detach().cpu().tolist())

        threshold = float(loaded.config.authenticity_threshold)
        predictions = [int(value >= threshold) for value in fake_probabilities]
        both_classes = len(set(truth)) == 2
        roc_auc = (
            float(roc_auc_score(truth, fake_probabilities)) if both_classes else None
        )
        pr_auc = (
            float(average_precision_score(truth, fake_probabilities))
            if both_classes
            else None
        )
        matrix = confusion_matrix(truth, predictions, labels=[0, 1]).tolist()
        report = EvaluationReport(
            report_no=str(uuid4()),
            model_version_id=model_row.id,
            dataset_name=request.dataset_name,
            dataset_split=request.dataset_split,
            dataset_sha256=sha256_file(path),
            sample_count=len(truth),
            accuracy=float(accuracy_score(truth, predictions)),
            precision_score=float(
                precision_score(truth, predictions, zero_division=0)
            ),
            recall_score=float(recall_score(truth, predictions, zero_division=0)),
            f1_score=float(f1_score(truth, predictions, zero_division=0)),
            auc_score=roc_auc,
            pr_auc_score=pr_auc,
            roc_auc_score=roc_auc,
            confusion_matrix={"labels": ["real", "fake"], "matrix": matrix},
            threshold_config={"fake_probability": threshold},
            report_status="success",
            created_by=created_by,
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def report(self, report_id):
        return self.db.get(ReportMetadata, report_id)

    def create_report(self, task_no):
        task = DetectionRepository(self.db).task_by_no(task_no)
        if task is None:
            return None
        rows = self.db.scalars(
            select(DetectionResult).where(DetectionResult.task_id == task.id)
        ).all()

        def counts(values):
            output = {}
            for value in values:
                output[str(value)] = output.get(str(value), 0) + 1
            return output

        summary = {
            "total_count": task.total_count,
            "success_count": task.success_count,
            "failed_count": task.failed_count,
            "authenticity_distribution": counts(
                row.authenticity_label for row in rows
            ),
            "risk_level_distribution": counts(row.risk_level for row in rows),
            "behavior_evidence_distribution": counts(
                "available" if row.behavior_available else "insufficient"
                for row in rows
            ),
            "model_version": (
                task.model_version.version if task.model_version else None
            ),
            "data_source": "real_model" if task.model_version else "unknown",
            "is_mock": False,
            "is_proxy_task": True,
        }
        report = ReportMetadata(
            report_no=str(uuid4()),
            task_id=task.id,
            status="succeeded",
            summary=summary,
        )
        self.db.add(report)
        self.db.commit()
        return report, task
