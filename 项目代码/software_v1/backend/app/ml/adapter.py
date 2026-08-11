"""Online, label-free adapter for the GRU fusion detector."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib
import math
from typing import Any, Iterable, Sequence

import numpy as np

from app.ml.loader import LoadedModel, ModelLoadError, load_model_from_environment


class ModelNotReady(ModelLoadError):
    """Raised when the configured model is unavailable for inference."""


@dataclass(frozen=True)
class PredictionResult:
    authenticity: str
    authenticity_scores: dict[str, float]
    confidence: float
    semantic_scores: dict[str, float]
    semantic_type: str
    behavior_scores: dict[str, float]
    behavior_type: str
    behavior_available: bool
    history_length: int
    semantic_weight: float
    behavior_weight: float
    weight_summary: str
    risk_source: str
    action: str
    route: str
    reason: str
    disclaimers: tuple[str, str, str, str] = (
        "门控权重是融合权重摘要，不是因果归因。",
        "语义和行为细分类分数是未经校准的相对匹配度。",
        "行为二分类使用原始真假标签作为代理任务，并非独立异常行为真值。",
        "检测结果是辅助审核建议，不替代人工事实认定。",
    )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


SEMANTIC_KEYS = ("real", "misleading", "exaggerated", "advertising")
BEHAVIOR_KEYS = (
    "normal",
    "review_manipulation",
    "crowdturfing",
    "bot_like",
    "insufficient_evidence",
)


def _core_routing():
    try:
        return importlib.import_module("spam_cascade.routing").DecisionRouter
    except ModuleNotFoundError as exc:
        raise ModelNotReady("model core routing dependencies are not installed") from exc


def _as_float_list(values: Any, expected: int, name: str) -> list[float]:
    result = [float(value) for value in values]
    if len(result) != expected or not all(math.isfinite(value) for value in result):
        raise ValueError(f"{name} must contain {expected} finite values")
    return result


class ModelAdapter:
    """Translate API requests into the frozen GRU model tensor contract."""

    def __init__(self, loaded_model: LoadedModel | None = None):
        self._loaded_model = loaded_model

    @property
    def loaded_model(self) -> LoadedModel:
        if self._loaded_model is None:
            try:
                self._loaded_model = load_model_from_environment()
            except ModelLoadError as exc:
                raise ModelNotReady(str(exc)) from exc
        return self._loaded_model

    @staticmethod
    def _history_features(request: Any) -> list[np.ndarray]:
        history = getattr(request, "behavior_history", None)
        if history is None:
            history = getattr(request, "history", ())
        items = list(history or ())
        target_date = getattr(request, "date", None)
        review_ids: list[str] = []
        for item in items:
            item_date = getattr(item, "date", item.get("date") if isinstance(item, dict) else None)
            if target_date is not None and item_date is not None and item_date >= target_date:
                raise ValueError("behavior history must contain only past events")
            review_id = getattr(item, "review_id", item.get("review_id") if isinstance(item, dict) else None)
            if review_id is not None:
                review_ids.append(str(review_id))
        if len(review_ids) != len(set(review_ids)):
            raise ValueError("behavior history review_id values must be unique")
        items.sort(
            key=lambda item: (
                getattr(item, "date", item.get("date") if isinstance(item, dict) else None),
                str(getattr(item, "review_id", item.get("review_id") if isinstance(item, dict) else "")),
            )
        )
        features: list[np.ndarray] = []
        for item in items:
            values = getattr(item, "features", item.get("features") if isinstance(item, dict) else None)
            if values is None:
                raise ValueError("each behavior history item must provide 10 features")
            vector = np.asarray(values, dtype=np.float32)
            if vector.shape != (10,) or not np.isfinite(vector).all():
                raise ValueError("each behavior history item must provide 10 finite features")
            features.append(vector)
        return features

    @staticmethod
    def _current_features(request: Any, history: Sequence[np.ndarray]) -> np.ndarray:
        rating = float(getattr(request, "rating"))
        text = str(getattr(request, "text"))
        if not 0.0 <= rating <= 5.0:
            raise ValueError("rating must be between 0 and 5")
        prior_ratings = [float(vector[1]) * 5.0 for vector in history]
        mean = float(np.mean(prior_ratings)) if prior_ratings else rating
        std = float(np.std(prior_ratings)) if len(prior_ratings) > 1 else 0.0
        return np.asarray(
            [
                0.0,
                rating / 5.0,
                mean / 5.0,
                std / 5.0,
                abs(rating - mean) / 4.0,
                float(rating in (1.0, 5.0)),
                np.log1p(len(history)),
                0.0,
                0.0,
                np.log1p(len(text)) / 10.0,
            ],
            dtype=np.float32,
        )

    def _sequence(self, request: Any, minimum_history: int, maximum_history: int):
        history = self._history_features(request)
        current = self._current_features(request, history)
        sequence = history[-max(maximum_history - 1, 0) :] + [current]
        available = float(len(history) >= minimum_history)
        return np.stack(sequence), len(history), available

    def predict(self, request: Any) -> PredictionResult:
        loaded = self.loaded_model
        import torch

        sequence, history_length, available = self._sequence(
            request,
            loaded.config.minimum_history,
            loaded.config.maximum_history,
        )
        encoded = loaded.tokenizer(
            str(getattr(request, "text")),
            max_length=loaded.config.max_length,
            truncation=True,
            padding="max_length",
            return_tensors="pt",
        )
        batch: dict[str, Any] = {
            key: value.to(loaded.device) for key, value in encoded.items()
        }
        batch["sequence"] = torch.from_numpy(sequence).unsqueeze(0).to(loaded.device)
        batch["lengths"] = torch.tensor([len(sequence)], dtype=torch.long, device=loaded.device)
        batch["behavior_available"] = torch.tensor([available], dtype=torch.float32, device=loaded.device)
        with torch.no_grad():
            output = loaded.model(**batch)

        fusion = output.fusion
        behavior = output.behavior
        auth = torch.softmax(fusion.authenticity_logits[0], dim=-1).detach().cpu().tolist()
        semantic = fusion.semantic_match_scores[0].detach().cpu().tolist()
        behavior_scores = behavior.relative_probabilities[0].detach().cpu().tolist()
        auth = _as_float_list(auth, 2, "authenticity scores")
        semantic = _as_float_list(semantic, 4, "semantic scores")
        behavior_scores = _as_float_list(behavior_scores, 5, "behavior scores")
        semantic_map = dict(zip(SEMANTIC_KEYS, semantic, strict=True))
        behavior_map = dict(zip(BEHAVIOR_KEYS, behavior_scores, strict=True))
        router = _core_routing()(loaded.config)
        route = router.route(auth, semantic, history_length)
        decision = router.finalize(
            route,
            behavior_label=BEHAVIOR_KEYS[max(range(5), key=behavior_scores.__getitem__)],
            behavior_confidence=max(behavior_scores),
            fusion_authenticity_probabilities=auth,
            fusion_semantic_probabilities=semantic,
        )
        semantic_weight = float(fusion.gate_weights[0].mean().detach().cpu())
        semantic_weight = min(max(semantic_weight, 0.0), 1.0)
        return PredictionResult(
            authenticity=decision.authenticity,
            authenticity_scores={"real": auth[0], "fake": auth[1]},
            confidence=min(max(float(decision.confidence), 0.0), 1.0),
            semantic_scores=semantic_map,
            semantic_type=decision.semantic_type,
            behavior_scores=behavior_map,
            behavior_type=decision.behavior_type,
            behavior_available=bool(available),
            history_length=history_length,
            semantic_weight=semantic_weight,
            behavior_weight=1.0 - semantic_weight,
            weight_summary="semantic/behavior gate mean; not causal attribution",
            risk_source=decision.risk_source,
            action=decision.action,
            route=route.route,
            reason=route.reason,
        )
