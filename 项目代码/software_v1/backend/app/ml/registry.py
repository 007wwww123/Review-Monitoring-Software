"""Register the immutable model that is actually loaded by this process."""

from dataclasses import asdict

from sqlalchemy import select

from app.ml.loader import LoadedModel, ModelLoadError
from app.models import ModelVersion


def register_runtime_model(db, loaded: LoadedModel) -> ModelVersion:
    manifest = loaded.manifest
    if not manifest:
        raise ModelLoadError("loaded model does not contain a deployment manifest")
    version = loaded.model_version
    if not version or version == "unregistered":
        raise ModelLoadError("deployment manifest must contain a registered model version")
    row = db.scalar(select(ModelVersion).where(ModelVersion.version == version))
    if row is not None and row.checkpoint_sha256 != loaded.checkpoint_sha256:
        raise ModelLoadError("database model version uses a different checkpoint SHA-256")
    if row is None:
        row = ModelVersion(
            version=version,
            model_name=manifest["model"]["name"],
            checkpoint_path=str(loaded.checkpoint_path),
            checkpoint_sha256=loaded.checkpoint_sha256,
            tokenizer_name=manifest["tokenizer"]["name"],
            config_json=asdict(loaded.config),
            dataset_manifest_json=manifest["dataset"],
            metrics_json=manifest["metrics"].get("snapshot"),
        )
        db.add(row)
    for item in db.scalars(select(ModelVersion)).all():
        item.is_active = item is row
    row.is_active = True
    db.commit()
    db.refresh(row)
    return row
