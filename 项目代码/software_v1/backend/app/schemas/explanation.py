from __future__ import annotations

from pydantic import Field, model_validator

from .common import (Action, Authenticity, BehaviorType, Probability,
                     RiskSource, SemanticType, StrictModel)

SEMANTIC_KEYS = ("real", "misleading", "exaggerated", "advertising")
BEHAVIOR_KEYS = ("normal", "review_manipulation", "crowdturfing", "bot_like", "insufficient_evidence")


class FinalExplanation(StrictModel):
    authenticity: Authenticity
    confidence: Probability
    fake_probability: Probability
    threshold: Probability
    risk_source: RiskSource
    action: Action


class SemanticExplanation(StrictModel):
    authenticity_scores: dict[str, Probability]
    scores: dict[str, Probability]
    selected_type: SemanticType

    @model_validator(mode="after")
    def validate_keys(self):
        if tuple(self.authenticity_scores) != ("real", "fake"):
            raise ValueError("semantic authenticity scores must use real/fake order")
        if tuple(self.scores) != SEMANTIC_KEYS:
            raise ValueError("semantic scores must use the fixed four-label order")
        return self


class BehaviorExplanation(StrictModel):
    normality_scores: dict[str, Probability]
    scores: dict[str, Probability]
    selected_type: BehaviorType
    available: bool
    history_length: int = Field(ge=0, le=30)
    is_proxy_task: bool = True

    @model_validator(mode="after")
    def validate_keys(self):
        if tuple(self.normality_scores) != ("normal", "abnormal"):
            raise ValueError("behavior normality scores must use normal/abnormal order")
        if tuple(self.scores) != BEHAVIOR_KEYS:
            raise ValueError("behavior scores must use the fixed five-label order")
        if not self.available and self.selected_type != BehaviorType.insufficient_evidence:
            raise ValueError("unavailable behavior evidence must be insufficient_evidence")
        return self


class FusionExplanation(StrictModel):
    semantic_weight: Probability
    behavior_weight: Probability
    weight_summary: str = Field(min_length=1, max_length=500)


class EvidenceExplanation(StrictModel):
    semantic_evidence_state: str = Field(min_length=1, max_length=100)
    behavior_evidence_state: str = Field(min_length=1, max_length=100)
    calibration_state: str = Field(min_length=1, max_length=100)


class Explanation(StrictModel):
    schema_version: str = Field(pattern=r"^explanation\.v2$")
    final: FinalExplanation
    semantic: SemanticExplanation
    behavior: BehaviorExplanation
    fusion: FusionExplanation
    evidence: EvidenceExplanation
    limitations: tuple[str, str, str, str]

    @model_validator(mode="after")
    def validate_limitations(self):
        if len(self.limitations) != 4:
            raise ValueError("all four required limitations must be present")
        return self
