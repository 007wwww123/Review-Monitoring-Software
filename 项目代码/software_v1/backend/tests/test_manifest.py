import asyncio
import json
from pathlib import Path

import pytest

from app.main import app, lifespan
from app.ml.loader import ModelLoadError, load_model_from_environment
from app.ml.manifest import ManifestError, load_manifest


MANIFEST = Path(__file__).resolve().parents[2] / "configs" / "model_manifest.json"


def test_manifest_fixes_albert_gru_architecture_and_decision_boundary(tmp_path):
    manifest = load_manifest(MANIFEST)
    assert manifest["model"]["components"] == {
        "semantic": "ALBERT", "behavior": "GRU", "fusion": "vector_gate"
    }
    assert manifest["decision"]["allow_type_override"] is False

    invalid = json.loads(MANIFEST.read_text(encoding="utf-8"))
    invalid["model"]["components"]["behavior"] = "LSTM"
    target = tmp_path / "invalid.json"
    target.write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(ManifestError, match="ALBERT-GRU"):
        load_manifest(target)


def test_lifespan_loads_model_once_per_process(monkeypatch):
    for name in ("MODEL_CONFIG_PATH", "MODEL_CHECKPOINT_PATH", "MODEL_MANIFEST_PATH"):
        monkeypatch.setenv(name, "configured")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    loaded = object()
    calls = []

    def fake_load():
        calls.append(True)
        return loaded

    monkeypatch.setattr("app.main.load_model_from_environment", fake_load)

    async def exercise():
        async with lifespan(app):
            first = app.state.model_adapter
            assert first.loaded_model is loaded
            assert app.state.model_adapter is first

    asyncio.run(exercise())
    assert len(calls) == 1


def test_environment_loader_requires_local_albert_base(monkeypatch):
    for name in ("MODEL_CONFIG_PATH", "MODEL_CHECKPOINT_PATH", "MODEL_MANIFEST_PATH"):
        monkeypatch.setenv(name, "configured")
    monkeypatch.delenv("MODEL_BASE_PATH", raising=False)

    with pytest.raises(ModelLoadError, match="MODEL_BASE_PATH"):
        load_model_from_environment()
