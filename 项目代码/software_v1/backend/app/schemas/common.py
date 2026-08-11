from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, protected_namespaces=())


class Authenticity(str, Enum):
    real = "real"
    fake = "fake"


class SemanticType(str, Enum):
    real = "real"
    misleading = "misleading"
    exaggerated = "exaggerated"
    advertising = "advertising"
    none = "none"
    uncertain = "uncertain"


class BehaviorType(str, Enum):
    normal = "normal"
    review_manipulation = "review_manipulation"
    crowdturfing = "crowdturfing"
    bot_like = "bot_like"
    insufficient_evidence = "insufficient_evidence"


class RiskSource(str, Enum):
    real = "real"
    language_fake = "language_fake"
    behavior_fake = "behavior_fake"
    language_behavior_composite = "language_behavior_composite"
    uncertain = "uncertain"


class Action(str, Enum):
    keep = "keep"
    review = "review"
    block = "block"


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


Probability = Annotated[float, Field(ge=0.0, le=1.0)]


class BehaviorHistoryItem(StrictModel):
    review_id: str | None = Field(default=None, min_length=1, max_length=100)
    prod_id: str = Field(min_length=1, max_length=128)
    rating: float = Field(ge=0.0, le=5.0)
    date: datetime
    text: str = Field(default="", max_length=10000)

    @field_validator("date")
    @classmethod
    def date_has_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("behavior history date must include a timezone")
        return value


class ProbabilityMap(StrictModel):
    values: dict[str, Probability]

    @field_validator("values")
    @classmethod
    def no_empty_values(cls, value: dict[str, float]) -> dict[str, float]:
        if not value:
            raise ValueError("probability map cannot be empty")
        return value
