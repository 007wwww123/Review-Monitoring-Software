from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from .common import (Action, Authenticity, BehaviorHistoryItem, BehaviorType,
                     Probability, RiskSource, SemanticType, StrictModel,
                     TaskStatus)
from .explanation import Explanation


class SingleDetectionRequest(StrictModel):
    review_id: str | None = Field(default=None, min_length=1, max_length=100)
    user_id: str = Field(min_length=1, max_length=128)
    prod_id: str = Field(min_length=1, max_length=128)
    rating: float = Field(ge=0.0, le=5.0)
    date: datetime
    text: str = Field(min_length=1, max_length=10000)
    behavior_history: list[BehaviorHistoryItem] = Field(default_factory=list, max_length=30)

    @field_validator("date")
    @classmethod
    def date_has_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("date must include a timezone")
        return value

    @field_validator("behavior_history")
    @classmethod
    def history_is_past_only(cls, value: list[BehaviorHistoryItem], info):
        target_date = info.data.get("date")
        if target_date and any(item.date >= target_date for item in value):
            raise ValueError("behavior_history must contain only past events")
        return value


class BatchDetectionRequest(StrictModel):
    items: list[SingleDetectionRequest] = Field(min_length=1, max_length=1000)

    @field_validator("items")
    @classmethod
    def unique_review_ids(cls, value: list[SingleDetectionRequest]):
        ids = [item.review_id for item in value if item.review_id is not None]
        if len(ids) != len(set(ids)):
            raise ValueError("review_id must be unique within a batch")
        return value


class DetectionSubmitResponse(StrictModel):
    task_id: UUID
    status: TaskStatus
    created_at: datetime


class DetectionResultSummary(StrictModel):
    result_id: int
    review_id: str | None
    authenticity: Authenticity
    confidence: Probability
    semantic_type: SemanticType
    behavior_type: BehaviorType
    risk_source: RiskSource
    action: Action
    model_version: str


class SingleDetectionResponse(StrictModel):
    task: DetectionSubmitResponse
    result: DetectionResultSummary


class DetectionResultResponse(StrictModel):
    result_id: UUID
    review_id: str | None
    authenticity: Authenticity
    confidence: Probability
    semantic_type: SemanticType
    behavior_type: BehaviorType
    risk_source: RiskSource
    action: Action
    model_version: str
    explanation: Explanation
    created_at: datetime


class TaskStatusResponse(StrictModel):
    task_id: UUID
    status: TaskStatus
    total_count: int = Field(ge=0)
    completed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    error_summary: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
