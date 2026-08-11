"""Controlled loading boundary for the GRU fusion detector."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib
import os
from pathlib import Path
import sys
from typing import Any

from app.ml.manifest import ManifestError, load_manifest, sha256_file


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
    model_version: str = "unregistered"
    manifest: dict[str, Any] | None = None


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
    required_prefixes = {
        "ALBERT semantic": "semantic.encoder.",
        "GRU behavior": "behavior.gru.",
        "gated fusion": "fusion.",
    }
    missing = [name for name, prefix in required_prefixes.items() if not any(key.startswith(prefix) for key in state)]
    if missing:
        raise ModelLoadError(f"checkpoint is not a complete ALBERT-GRU fusion model: {', '.join(missing)}")
    return state


class ModelLoader:
    """Load one trusted, immutable GRU fusion model for process reuse."""

    def __init__(
        self,
        *,
        config_path: str | os.PathLike[str],
        checkpoint_path: str | os.PathLike[str],
        manifest_path: str | os.PathLike[str],
        base_model_path: str | os.PathLike[str] | None = None,
        tokenizer_path: str | os.PathLike[str] | None = None,
        model_root: str | os.PathLike[str] | None = None,
        expected_sha256: str | None = None,
        device: str = "auto",
        local_files_only: bool = True,
    ) -> None:
        self.config_path = Path(config_path).resolve()
        self.checkpoint_path = Path(checkpoint_path).resolve()
        self.manifest_path = Path(manifest_path).resolve()
        self.base_model_path = Path(base_model_path).resolve() if base_model_path else None
        self.tokenizer_path = Path(tokenizer_path).resolve() if tokenizer_path else None
        self.model_root = Path(model_root).resolve() if model_root else None
        self.expected_sha256 = expected_sha256
        self.device_name = device
        self.local_files_only = local_files_only

    def _validate_paths(self) -> None:
        if not self.manifest_path.is_file():
            raise ModelLoadError(f"model manifest does not exist: {self.manifest_path}")
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
        try:
            manifest = load_manifest(self.manifest_path)
        except ManifestError as exc:
            raise ModelLoadError(str(exc)) from exc
        if manifest["status"] != "ready":
            raise ModelLoadError("model manifest status must be ready before deployment")
        deployment_root = self.manifest_path.parent.parent
        manifest_checkpoint = (deployment_root / manifest["checkpoint"]["relative_path"]).resolve()
        if manifest_checkpoint != self.checkpoint_path:
            raise ModelLoadError("checkpoint path does not match model_manifest.json")
        manifest_config = (deployment_root / manifest["model"]["config_relative_path"]).resolve()
        if manifest_config != self.config_path:
            raise ModelLoadError("config path does not match model_manifest.json")
        expected_checkpoint_hash = manifest["checkpoint"].get("sha256")
        expected_config_hash = manifest["checkpoint"].get("config_sha256")
        if not expected_checkpoint_hash or sha256_file(self.checkpoint_path) != expected_checkpoint_hash:
            raise ModelLoadError("checkpoint SHA-256 does not match model_manifest.json")
        if not expected_config_hash or sha256_file(self.config_path) != expected_config_hash:
            raise ModelLoadError("config SHA-256 does not match model_manifest.json")
        config_module, modeling_module = _model_core_imports()
        import torch
        from transformers import AutoTokenizer

        config = config_module.CascadeConfig.from_json(self.config_path)
        config.authenticity_threshold = float(manifest["decision"]["authenticity_threshold"])
        config.allow_type_override = False
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
            model_version=str(manifest["model"]["version"]),
            manifest=manifest,
        )


def load_model_from_environment() -> LoadedModel:
    """Load only paths supplied by deployment configuration, never a request."""
    config = os.getenv("MODEL_CONFIG_PATH")
    checkpoint = os.getenv("MODEL_CHECKPOINT_PATH")
    manifest = os.getenv("MODEL_MANIFEST_PATH")
    base_model = os.getenv("MODEL_BASE_PATH")
    if not config or not checkpoint or not manifest:
        raise ModelLoadError("MODEL_CONFIG_PATH, MODEL_CHECKPOINT_PATH and MODEL_MANIFEST_PATH are required")
    if not base_model:
        raise ModelLoadError(
            "MODEL_BASE_PATH is required for reproducible offline ALBERT loading"
        )
    return ModelLoader(
        config_path=config,
        checkpoint_path=checkpoint,
        manifest_path=manifest,
        base_model_path=base_model,
        tokenizer_path=os.getenv("MODEL_TOKENIZER_PATH"),
        model_root=os.getenv("MODEL_ROOT"),
        expected_sha256=os.getenv("MODEL_CHECKPOINT_SHA256"),
        device=os.getenv("MODEL_DEVICE", "auto"),
    ).load()
