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
    ) -> FinalDecision:
        if fusion_authenticity_probabilities is None or fusion_semantic_probabilities is None:
            raise ValueError("fusion probabilities are required for run_fusion route")
        fusion_auth = list(fusion_authenticity_probabilities)
        fusion_semantic = list(fusion_semantic_probabilities)
        if len(fusion_auth) != 2 or len(fusion_semantic) != len(self.config.semantic_labels):
            raise ValueError("fusion probability dimensions do not match configuration")

        authenticity = (
            "fake"
            if fusion_auth[1] >= self.config.authenticity_threshold
            else "real"
        )
        semantic_index = max(range(len(fusion_semantic)), key=fusion_semantic.__getitem__)
        semantic_label = self.config.semantic_labels[semantic_index]
        fusion_confidence = fusion_auth[1] if authenticity == "fake" else fusion_auth[0]
        if behavior_label is None or behavior_confidence is None:
            if not route.behavior_available:
                behavior_label = "insufficient_evidence"
                behavior_confidence = 1.0
            else:
                raise ValueError("behavior output is required for run_fusion route")

        if not route.behavior_available:
            behavior_label = "insufficient_evidence"
            behavior_confidence = 1.0

        behavior_abnormal = behavior_label not in {"normal", "insufficient_evidence"}
        semantic_abnormal = authenticity == "fake" and semantic_label != "real"
        if authenticity == "fake":
            if behavior_abnormal and semantic_abnormal:
                risk_source = "language_behavior_composite"
            elif semantic_abnormal:
                risk_source = "language_fake"
            elif behavior_abnormal:
                risk_source = "behavior_fake"
            else:
                risk_source = "uncertain"
            # Type matches describe supporting evidence only. They cannot turn a
            # real fusion result into fake or independently trigger blocking.
            return FinalDecision(
                "fake", semantic_label, behavior_label, risk_source, fusion_confidence, "review"
            )
        return FinalDecision(
            "real", semantic_label, behavior_label, "real", fusion_confidence, "keep"
        )
