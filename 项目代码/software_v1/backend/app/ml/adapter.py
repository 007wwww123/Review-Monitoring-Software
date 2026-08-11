"""Controlled boundary for loading the trained detector."""
import os
from pathlib import Path


class ModelNotReady(RuntimeError):
    pass


class ModelAdapter:
    def __init__(self, checkpoint_path: str | None = None):
        configured = checkpoint_path or os.getenv("MODEL_CHECKPOINT_PATH")
        self.checkpoint_path = Path(configured) if configured else None

    def predict(self, request):
        if self.checkpoint_path is None or not self.checkpoint_path.is_file():
            raise ModelNotReady("MODEL_CHECKPOINT_PATH must point to a trained checkpoint")
        raise ModelNotReady("trained checkpoint loading is not configured for this checkpoint format")
