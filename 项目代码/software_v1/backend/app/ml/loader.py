"""Controlled loading boundary for the GRU fusion detector."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib
import os
from pathlib import Path
import sys
from typing import Any


class ModelLoadError(RuntimeError):
    """Raised when a configured model cannot be loaded safely."""


@dataclass(frozen=True)
class LoadedModel:
    model: Any
    tokenizer: Any
    config: Any
    device: Any
    checkpoint_path: Path
    checkpoint_sha256: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _model_core_imports():
    """Import the bundled model core without relying on the process cwd."""
    try:
        config_module = importlib.import_module("spam_cascade.config")
        modeling_module = importlib.import_module("spam_cascade.modeling")
        return config_module, modeling_module
    except ModuleNotFoundError:
        core_root = Path(__file__).resolve().parents[3] / "model_core"
        if not core_root.is_dir():
            raise ModelLoadError(f"model core directory does not exist: {core_root}")
        sys.path.insert(0, str(core_root))
        try:
            config_module = importlib.import_module("spam_cascade.config")
            modeling_module = importlib.import_module("spam_cascade.modeling")
            return config_module, modeling_module
        except ModuleNotFoundError as exc:
            raise ModelLoadError("model core dependencies are not installed") from exc


def _load_state(path: Path, device: Any) -> dict[str, Any]:
    import torch

    try:
        payload = torch.load(path, map_location=device, weights_only=True)
    except TypeError:
        payload = torch.load(path, map_location=device)
    state = payload.get("model_state", payload) if isinstance(payload, dict) else payload
    if not isinstance(state, dict) or not state:
        raise ModelLoadError("checkpoint does not contain a non-empty state dictionary")
    if all(isinstance(key, str) and key.startswith("module.") for key in state):
        state = {key.removeprefix("module."): value for key, value in state.items()}
    if not all(isinstance(key, str) for key in state):
        raise ModelLoadError("checkpoint state keys must be strings")
    if any(key.startswith("behavior.lstm.") for key in state):
        raise ModelLoadError("LSTM checkpoint is incompatible with the configured GRU model")
    if not any(key.startswith("behavior.gru.") for key in state):
        raise ModelLoadError("checkpoint does not contain GRU behavior parameters")
    return state


class ModelLoader:
    """Load one trusted, immutable GRU fusion model for process reuse."""

    def __init__(
        self,
        *,
        config_path: str | os.PathLike[str],
        checkpoint_path: str | os.PathLike[str],
        base_model_path: str | os.PathLike[str] | None = None,
        tokenizer_path: str | os.PathLike[str] | None = None,
        model_root: str | os.PathLike[str] | None = None,
        expected_sha256: str | None = None,
        device: str = "auto",
        local_files_only: bool = True,
    ) -> None:
        self.config_path = Path(config_path).resolve()
        self.checkpoint_path = Path(checkpoint_path).resolve()
        self.base_model_path = Path(base_model_path).resolve() if base_model_path else None
        self.tokenizer_path = Path(tokenizer_path).resolve() if tokenizer_path else None
        self.model_root = Path(model_root).resolve() if model_root else None
        self.expected_sha256 = expected_sha256
        self.device_name = device
        self.local_files_only = local_files_only

    def _validate_paths(self) -> None:
        if not self.config_path.is_file():
            raise ModelLoadError(f"model config does not exist: {self.config_path}")
        if not self.checkpoint_path.is_file():
            raise ModelLoadError(f"model checkpoint does not exist: {self.checkpoint_path}")
        if self.checkpoint_path.suffixes[-2:] == [".tar", ".gz"]:
            raise ModelLoadError("extract the selected .pt checkpoint from the archive before loading")
        if self.model_root is not None:
            try:
                self.checkpoint_path.relative_to(self.model_root)
            except ValueError as exc:
                raise ModelLoadError("checkpoint must be inside the configured model root") from exc
        if self.expected_sha256 is not None:
            actual = _sha256(self.checkpoint_path)
            if actual.lower() != self.expected_sha256.lower():
                raise ModelLoadError("checkpoint SHA-256 does not match the configured manifest")

    def load(self) -> LoadedModel:
        self._validate_paths()
        config_module, modeling_module = _model_core_imports()
        import torch
        from transformers import AutoTokenizer

        config = config_module.CascadeConfig.from_json(self.config_path)
        if self.base_model_path is not None:
            if not self.base_model_path.is_dir():
                raise ModelLoadError(f"base model directory does not exist: {self.base_model_path}")
            config.albert_name_or_path = str(self.base_model_path)
        config.validate()
        if self.device_name == "auto":
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            device = torch.device(self.device_name)
        tokenizer_source = str(self.tokenizer_path or config.albert_name_or_path)
        try:
            tokenizer = AutoTokenizer.from_pretrained(
                tokenizer_source,
                local_files_only=self.local_files_only,
            )
            model = modeling_module.CascadeDetector(config).to(device)
            state = _load_state(self.checkpoint_path, device)
            model.load_state_dict(state, strict=True)
        except (OSError, RuntimeError, ValueError) as exc:
            raise ModelLoadError(f"failed to load GRU fusion model: {exc}") from exc
        model.eval()
        return LoadedModel(
            model=model,
            tokenizer=tokenizer,
            config=config,
            device=device,
            checkpoint_path=self.checkpoint_path,
            checkpoint_sha256=_sha256(self.checkpoint_path),
        )


def load_model_from_environment() -> LoadedModel:
    """Load only paths supplied by deployment configuration, never a request."""
    config = os.getenv("MODEL_CONFIG_PATH")
    checkpoint = os.getenv("MODEL_CHECKPOINT_PATH")
    if not config or not checkpoint:
        raise ModelLoadError("MODEL_CONFIG_PATH and MODEL_CHECKPOINT_PATH are required")
    return ModelLoader(
        config_path=config,
        checkpoint_path=checkpoint,
        base_model_path=os.getenv("MODEL_BASE_PATH"),
        tokenizer_path=os.getenv("MODEL_TOKENIZER_PATH"),
        model_root=os.getenv("MODEL_ROOT"),
        expected_sha256=os.getenv("MODEL_CHECKPOINT_SHA256"),
        device=os.getenv("MODEL_DEVICE", "auto"),
    ).load()
