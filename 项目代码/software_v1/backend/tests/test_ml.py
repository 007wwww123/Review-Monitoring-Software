from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

import pytest

torch = pytest.importorskip("torch")

MODEL_CORE = Path(__file__).resolve().parents[2] / "model_core"
sys.path.insert(0, str(MODEL_CORE))

from app.ml.adapter import ModelAdapter
from app.ml.loader import ModelLoadError, _load_state
from app.ml.loader import LoadedModel
from spam_cascade.config import CascadeConfig


class FakeTokenizer:
    def __call__(self, text, **kwargs):
        return {
            "input_ids": torch.ones(1, kwargs["max_length"], dtype=torch.long),
            "attention_mask": torch.ones(1, kwargs["max_length"], dtype=torch.long),
        }


class FakeModel:
    def __init__(self):
        self.calls = []

    def __call__(self, **batch):
        self.calls.append(batch)
        available = bool(batch["behavior_available"].item())
        behavior_scores = (
            [0.7, 0.1, 0.1, 0.1, 0.0]
            if available
            else [0.0, 0.0, 0.0, 0.0, 1.0]
        )
        return SimpleNamespace(
            fusion=SimpleNamespace(
                authenticity_logits=torch.tensor([[0.0, 2.0]]),
                text_authenticity_probabilities=torch.tensor([[0.2, 0.8]]),
                behavior_normality_probabilities=torch.tensor([[0.7, 0.3]]),
                semantic_match_scores=torch.tensor([[0.8, 0.1, 0.05, 0.05]]),
                gate_weights=torch.ones(1, 256) if available else torch.ones(1, 256),
            ),
            behavior=SimpleNamespace(
                relative_probabilities=torch.tensor([behavior_scores]),
            ),
        )


def _loaded(model=None):
    return LoadedModel(
        model=model or FakeModel(),
        tokenizer=FakeTokenizer(),
        config=CascadeConfig(),
        device=torch.device("cpu"),
        checkpoint_path=Path("checkpoint.pt"),
        checkpoint_sha256="0" * 64,
    )


def _request(history=()):
    return SimpleNamespace(
        review_id="target", user_id="user", prod_id="product", rating=4.0,
        date=datetime(2026, 8, 10, tzinfo=timezone.utc),
        text="review text", behavior_history=list(history),
    )


def _history_item(index):
    return SimpleNamespace(
        review_id=f"history-{index}", prod_id=f"product-{index % 3}",
        rating=float(index % 5 + 1),
        date=datetime(2026, 8, 10, tzinfo=timezone.utc) - timedelta(hours=36-index),
        text=f"history text {index}",
    )


def test_loader_accepts_gru_state_and_rejects_lstm_state(tmp_path):
    gru_path = tmp_path / "gru.pt"
    torch.save({
        "semantic.encoder.weight": torch.ones(1),
        "behavior.gru.weight_ih_l0": torch.ones(3, 10),
        "fusion.authenticity_head.weight": torch.ones(1),
    }, gru_path)
    state = _load_state(gru_path, torch.device("cpu"))
    assert "behavior.gru.weight_ih_l0" in state

    lstm_path = tmp_path / "lstm.pt"
    torch.save({"behavior.lstm.weight_ih_l0": torch.ones(4, 10)}, lstm_path)
    with pytest.raises(ModelLoadError, match="LSTM checkpoint"):
        _load_state(lstm_path, torch.device("cpu"))


def test_adapter_runs_fusion_and_marks_missing_history():
    fake = FakeModel()
    result = ModelAdapter(_loaded(fake)).predict(_request())
    assert result.route == "run_fusion"
    assert result.behavior_available is False
    assert result.behavior_type == "insufficient_evidence"
    assert tuple(result.semantic_scores) == (
        "real", "misleading", "exaggerated", "advertising"
    )
    assert tuple(result.behavior_scores) == (
        "normal", "review_manipulation", "crowdturfing", "bot_like", "insufficient_evidence"
    )
    assert fake.calls[0]["sequence"].shape == (1, 1, 10)


def test_adapter_uses_only_bounded_history_and_gru_sequence():
    fake = FakeModel()
    history = [_history_item(index) for index in range(35)]
    result = ModelAdapter(_loaded(fake)).predict(_request(history))
    assert result.behavior_available is True
    assert result.history_length == 35
    assert fake.calls[0]["sequence"].shape == (1, 30, 10)
    # The target event is always the final time step.
    assert fake.calls[0]["sequence"][0, -1, 1].item() == pytest.approx(0.8)
