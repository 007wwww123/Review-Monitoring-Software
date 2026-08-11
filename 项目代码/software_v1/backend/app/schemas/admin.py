from datetime import datetime
from pydantic import Field
from .common import StrictModel
from .common import Action, Authenticity, BehaviorType, Probability, RiskSource, SemanticType
from .explanation import Explanation

class ErrorResponse(StrictModel):
    code: str
    message: str
    request_id: str | None = None

class ModelResponse(StrictModel):
    version: str; model_name: str; tokenizer_name: str; config: dict; metrics: dict | None
    checkpoint_sha256: str; is_active: bool; created_at: datetime

class EvaluationRequest(StrictModel):
    dataset_name: str = Field(min_length=1, max_length=100)
    dataset_split: str = Field(pattern="^(train|val|test|production_review)$")
    tsv_path: str = Field(min_length=1, max_length=500)

class EvaluationResponse(StrictModel):
    report_id: int; dataset_name: str; dataset_split: str; sample_count: int
    accuracy: float | None; precision: float | None; recall: float | None; f1: float | None; auc: float | None
    confusion_matrix: dict | None; status: str; created_at: datetime

class ResultResponse(StrictModel):
    result_id: int; task_id: str; review_id: str | None; authenticity: Authenticity; confidence: Probability
    semantic_type: SemanticType; behavior_type: BehaviorType; risk_source: RiskSource; action: Action; model_version: str
    user_key: str | None; product_id: str | None; text_excerpt: str
    data_source: str; is_mock: bool; is_proxy_task: bool
    explanation: Explanation | None; created_at: datetime

class ResultPage(StrictModel):
    items: list[ResultResponse]; page: int; page_size: int; total: int

class ReportRequest(StrictModel):
    task_id: str

class ReportResponse(StrictModel):
    report_id: int; task_id: str; status: str; summary: dict; created_at: datetime
