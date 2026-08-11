"""Online, label-free adapter for the GRU fusion detector."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib
import math
from typing import Any

from app.ml.loader import LoadedModel, ModelLoadError, load_model_from_environment


class ModelNotReady(ModelLoadError):
    """Raised when the configured model is unavailable for inference."""


@dataclass(frozen=True)
class PredictionResult:
    authenticity: str
    authenticity_scores: dict[str, float]
    threshold: float
    confidence: float
    semantic_authenticity_scores: dict[str, float]
    semantic_scores: dict[str, float]
    semantic_type: str
    behavior_scores: dict[str, float]
    behavior_normality_scores: dict[str, float]
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
    limitations: tuple[str, str, str, str] = (
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


def _core_feature_builder():
    try:
        return importlib.import_module("spam_cascade.data").BehaviorFeatureBuilder
    except ModuleNotFoundError as exc:
        raise ModelNotReady("model core feature dependencies are not installed") from exc


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

    def _sequence(self, request: Any, minimum_history: int, maximum_history: int):
        history = list(getattr(request, "behavior_history", ()) or ())
        builder = _core_feature_builder()(
            minimum_history=minimum_history,
            maximum_history=maximum_history,
        )
        return builder.build_inference_sequence(history, request)

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
        semantic_auth = fusion.text_authenticity_probabilities[0].detach().cpu().tolist()
        behavior_normality = fusion.behavior_normality_probabilities[0].detach().cpu().tolist()
        semantic = fusion.semantic_match_scores[0].detach().cpu().tolist()
        behavior_scores = behavior.relative_probabilities[0].detach().cpu().tolist()
        auth = _as_float_list(auth, 2, "authenticity scores")
        semantic_auth = _as_float_list(semantic_auth, 2, "semantic authenticity scores")
        behavior_normality = _as_float_list(behavior_normality, 2, "behavior normality scores")
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
            threshold=float(loaded.config.authenticity_threshold),
            confidence=min(max(float(decision.confidence), 0.0), 1.0),
            semantic_authenticity_scores={"real": semantic_auth[0], "fake": semantic_auth[1]},
            semantic_scores=semantic_map,
            semantic_type=decision.semantic_type,
            behavior_scores=behavior_map,
            behavior_normality_scores={
                "normal": behavior_normality[0],
                "abnormal": behavior_normality[1],
            },
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
