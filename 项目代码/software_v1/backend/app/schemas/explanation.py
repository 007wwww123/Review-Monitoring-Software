from __future__ import annotations

from pydantic import Field, model_validator

from .common import (Action, Authenticity, BehaviorType, Probability,
                     RiskSource, SemanticType, StrictModel)

SEMANTIC_KEYS = ("real", "misleading", "exaggerated", "advertising")
BEHAVIOR_KEYS = ("normal", "review_manipulation", "crowdturfing", "bot_like", "insufficient_evidence")


class FinalExplanation(StrictModel):
    authenticity: Authenticity
    confidence: Probability
    risk_source: RiskSource
    action: Action


class SemanticExplanation(StrictModel):
    scores: dict[str, Probability]
    selected_type: SemanticType

    @model_validator(mode="after")
    def validate_keys(self):
        if tuple(self.scores) != SEMANTIC_KEYS:
            raise ValueError("semantic scores must use the fixed four-label order")
        return self


class BehaviorExplanation(StrictModel):
    scores: dict[str, Probability]
    selected_type: BehaviorType
    available: bool
    history_length: int = Field(ge=0, le=30)
    is_proxy_task: bool = True

    @model_validator(mode="after")
    def validate_keys(self):
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
    schema_version: str = Field(pattern=r"^explanation\.v1$")
    final: FinalExplanation
    semantic: SemanticExplanation
    behavior: BehaviorExplanation
    fusion: FusionExplanation
    evidence: EvidenceExplanation
    disclaimers: tuple[str, str, str, str]

    @model_validator(mode="after")
    def validate_disclaimers(self):
        if len(self.disclaimers) != 4:
            raise ValueError("all four required disclaimers must be present")
        return self
