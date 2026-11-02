from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Optional

from .config import CascadeConfig


@dataclass(frozen=True)
class RouteDecision:
    route: str
    semantic_label: str
    confidence: float
    reason: str
    behavior_available: bool = True


@dataclass(frozen=True)
class FinalDecision:
    authenticity: str
    semantic_type: str
    behavior_type: str
    risk_source: str
    confidence: float
    action: str
    authenticity_probabilities: tuple[float, float] = (0.0, 0.0)
    semantic_match_scores: tuple[float, ...] = ()
    behavior_match_scores: tuple[float, ...] = ()
    semantic_match_calibrated: bool = False
    behavior_match_calibrated: bool = False
    gate_weights: tuple[float, ...] = ()


def normalized_entropy(probabilities: Iterable[float]) -> float:
    values = [max(float(value), 1e-12) for value in probabilities]
    total = sum(values)
    values = [value / total for value in values]
    if len(values) <= 1:
        return 0.0
    return -sum(value * math.log(value) for value in values) / math.log(len(values))


class DecisionRouter:
    """Mandatory dual-stream router; every review reaches GRU and fusion."""

    def __init__(self, config: CascadeConfig) -> None:
        config.validate()
        self.config = config

    def route(
        self,
        authenticity_probabilities: Iterable[float],
        semantic_probabilities: Iterable[float],
        history_length: int,
        behavior_trigger_score: float = 0.0,
    ) -> RouteDecision:
        auth = list(authenticity_probabilities)
        semantic = list(semantic_probabilities)
        if len(auth) != 2 or len(semantic) != len(self.config.semantic_labels):
            raise ValueError("probability dimensions do not match configuration")

        real_probability, fake_probability = auth
        semantic_index = max(range(len(semantic)), key=semantic.__getitem__)
        semantic_label = self.config.semantic_labels[semantic_index]
        return RouteDecision(
            "run_fusion",
            semantic_label,
            max(real_probability, fake_probability),
            "mandatory_semantic_behavior_fusion",
            history_length >= self.config.minimum_history,
        )

    def finalize(
        self,
        route: RouteDecision,
        behavior_label: Optional[str] = None,
        behavior_confidence: Optional[float] = None,
        fusion_authenticity_probabilities: Optional[Iterable[float]] = None,
        fusion_semantic_probabilities: Optional[Iterable[float]] = None,
        semantic_match_scores: Optional[Iterable[float]] = None,
        behavior_match_scores: Optional[Iterable[float]] = None,
        gate_weights: Optional[Iterable[float]] = None,
        semantic_match_calibrated: bool = False,
        behavior_match_calibrated: bool = False,
    ) -> FinalDecision:
        if fusion_authenticity_probabilities is None or fusion_semantic_probabilities is None:
            raise ValueError("fusion probabilities are required for run_fusion route")
        fusion_auth = list(fusion_authenticity_probabilities)
        fusion_semantic = list(fusion_semantic_probabilities)
        if len(fusion_auth) != 2 or len(fusion_semantic) != len(self.config.semantic_labels):
            raise ValueError("fusion probability dimensions do not match configuration")
        semantic_values = (
            fusion_semantic if semantic_match_scores is None else semantic_match_scores
        )
        behavior_values = () if behavior_match_scores is None else behavior_match_scores
        gate_values = () if gate_weights is None else gate_weights
        semantic_scores = tuple(float(value) for value in semantic_values)
        behavior_scores = tuple(float(value) for value in behavior_values)
        gates = tuple(float(value) for value in gate_values)

        def decision(*args: object) -> FinalDecision:
            return FinalDecision(
                *args,
                authenticity_probabilities=(float(fusion_auth[0]), float(fusion_auth[1])),
                semantic_match_scores=semantic_scores,
                behavior_match_scores=behavior_scores,
                semantic_match_calibrated=semantic_match_calibrated,
                behavior_match_calibrated=behavior_match_calibrated,
                gate_weights=gates,
            )

        authenticity = "fake" if fusion_auth[1] >= fusion_auth[0] else "real"
        semantic_index = max(range(len(fusion_semantic)), key=fusion_semantic.__getitem__)
        semantic_label = self.config.semantic_labels[semantic_index]
        fusion_confidence = min(max(fusion_auth), max(fusion_semantic))
        if behavior_label is None or behavior_confidence is None:
            if not route.behavior_available:
                behavior_label = "insufficient_evidence"
                behavior_confidence = 1.0
            else:
                raise ValueError("behavior output is required for run_fusion route")

        behavior_abnormal = behavior_label not in {"normal", "insufficient_evidence"}
        semantic_abnormal = authenticity == "fake" and semantic_label != "real"
        if behavior_abnormal and semantic_abnormal:
            return decision(
                "fake",
                semantic_label,
                behavior_label,
                "language_behavior_composite",
                min(max(fusion_confidence, behavior_confidence), 1.0),
                "block",
            )
        if behavior_abnormal:
            return decision(
                "fake", "none", behavior_label, "behavior_fake", behavior_confidence, "review"
            )
        if semantic_abnormal:
            return decision(
                "fake", semantic_label, behavior_label, "language_fake", fusion_confidence, "review"
            )
        if authenticity == "fake":
            return decision(
                "fake", "uncertain", behavior_label, "uncertain", fusion_confidence, "review"
            )
        return decision(
            "real", "real", behavior_label, "real", fusion_confidence, "keep"
        )
