from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.mysql import MEDIUMTEXT

from app.db.base import Base


def pk_column() -> Mapped[int]:
    # SQLite needs INTEGER for implicit autoincrement; MySQL still receives BIGINT.
    return mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)


class SysUser(Base):
    __tablename__ = "sys_user"

    id: Mapped[int] = pk_column()
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(Enum("admin", "reviewer", "operator", name="sys_user_role"), default="reviewer", nullable=False)
    status: Mapped[str] = mapped_column(Enum("active", "disabled", "locked", name="sys_user_status"), default="active", nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    tasks: Mapped[list["DetectionTask"]] = relationship(back_populates="creator")


class ReviewEvent(Base):
    __tablename__ = "review_event"
    __table_args__ = (
        CheckConstraint("rating IS NULL OR (rating >= 0 AND rating <= 5)", name="ck_review_rating_range"),
        UniqueConstraint("source_type", "external_review_id", name="uq_review_source_external"),
        Index("idx_review_created", "created_at"),
        Index("idx_review_source", "source_type", "created_at"),
        Index("idx_review_text_hash", "text_sha256"),
        Index("idx_review_manual_label", "manual_label", "created_at"),
    )

    id: Mapped[int] = pk_column()
    source_type: Mapped[str] = mapped_column(Enum("online", "manual_validation", "manual_review", name="review_source_type"), nullable=False)
    external_review_id: Mapped[str | None] = mapped_column(String(100))
    user_key: Mapped[str | None] = mapped_column(String(64), index=True)
    product_key: Mapped[str | None] = mapped_column(String(64), index=True)
    rating: Mapped[float | None] = mapped_column(Numeric(3, 1))
    review_date: Mapped[date | None] = mapped_column(Date)
    review_text: Mapped[str] = mapped_column(Text().with_variant(MEDIUMTEXT, "mysql"), nullable=False)
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    manual_label: Mapped[str] = mapped_column(Enum("real", "fake", "unknown", name="review_manual_label"), default="unknown", nullable=False)
    manual_label_by: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id", ondelete="SET NULL"))
    manual_label_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ModelVersion(Base):
    __tablename__ = "model_version"

    id: Mapped[int] = pk_column()
    version: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    checkpoint_path: Mapped[str] = mapped_column(String(500), nullable=False)
    checkpoint_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    tokenizer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    dataset_manifest_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    metrics_json: Mapped[dict | None] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime)

    tasks: Mapped[list["DetectionTask"]] = relationship(back_populates="model_version")
    results: Mapped[list["DetectionResult"]] = relationship(back_populates="model_version")


class DetectionTask(Base):
    __tablename__ = "detection_task"

    id: Mapped[int] = pk_column()
    task_no: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    task_type: Mapped[str] = mapped_column(Enum("single", "batch", "evaluation", name="detection_task_type"), nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id", ondelete="SET NULL"))
    model_version_id: Mapped[int | None] = mapped_column(ForeignKey("model_version.id", ondelete="SET NULL"))
    input_file_name: Mapped[str | None] = mapped_column(String(255))
    input_file_sha256: Mapped[str | None] = mapped_column(String(64))
    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(Enum("queued", "running", "success", "partial", "failed", "cancelled", name="detection_task_status"), default="queued", nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(1000))
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    creator: Mapped[SysUser | None] = relationship(back_populates="tasks")
    model_version: Mapped[ModelVersion | None] = relationship(back_populates="tasks")
    results: Mapped[list["DetectionResult"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class DetectionResult(Base):
    __tablename__ = "detection_result"
    __table_args__ = (
        CheckConstraint("authenticity_probability >= 0 AND authenticity_probability <= 1", name="ck_result_probability"),
        UniqueConstraint("task_id", "review_event_id", "model_version_id", name="uq_result_task_review_model"),
    )

    id: Mapped[int] = pk_column()
    task_id: Mapped[int] = mapped_column(ForeignKey("detection_task.id", ondelete="CASCADE"), nullable=False)
    review_event_id: Mapped[int] = mapped_column(ForeignKey("review_event.id", ondelete="RESTRICT"), nullable=False)
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_version.id", ondelete="RESTRICT"), nullable=False)
    authenticity_label: Mapped[str] = mapped_column(Enum("real", "fake", name="authenticity_label"), nullable=False)
    authenticity_probability: Mapped[float] = mapped_column(Numeric(8, 7), nullable=False)
    semantic_label: Mapped[str] = mapped_column(Enum("real", "misleading", "exaggerated", "advertising", name="semantic_label"), nullable=False)
    semantic_scores: Mapped[dict | None] = mapped_column(JSON)
    behavior_label: Mapped[str] = mapped_column(Enum("normal", "review_manipulation", "crowdturfing", "bot_like", "insufficient_evidence", name="behavior_label"), nullable=False)
    behavior_scores: Mapped[dict | None] = mapped_column(JSON)
    behavior_available: Mapped[bool] = mapped_column(Boolean, nullable=False)
    risk_level: Mapped[str] = mapped_column(Enum("low", "medium", "high", "unknown", name="risk_level"), nullable=False)
    risk_source: Mapped[dict | None] = mapped_column(JSON)
    recommendation: Mapped[str | None] = mapped_column(String(255))
    explanation: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    task: Mapped[DetectionTask] = relationship(back_populates="results")
    model_version: Mapped[ModelVersion] = relationship(back_populates="results")


class EvaluationReport(Base):
    __tablename__ = "evaluation_report"

    id: Mapped[int] = pk_column()
    report_no: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_version.id", ondelete="RESTRICT"), nullable=False)
    dataset_name: Mapped[str] = mapped_column(String(100), nullable=False)
    dataset_split: Mapped[str] = mapped_column(Enum("train", "val", "test", "production_review", name="evaluation_dataset_split"), nullable=False)
    dataset_sha256: Mapped[str | None] = mapped_column(String(64))
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    accuracy: Mapped[float | None] = mapped_column(Numeric(8, 7))
    precision_score: Mapped[float | None] = mapped_column(Numeric(8, 7))
    recall_score: Mapped[float | None] = mapped_column(Numeric(8, 7))
    f1_score: Mapped[float | None] = mapped_column(Numeric(8, 7))
    auc_score: Mapped[float | None] = mapped_column(Numeric(8, 7))
    confusion_matrix: Mapped[dict | None] = mapped_column(JSON)
    threshold_config: Mapped[dict | None] = mapped_column(JSON)
    report_status: Mapped[str] = mapped_column(Enum("success", "failed", name="evaluation_report_status"), nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class OperationLog(Base):
    __tablename__ = "operation_log"

    id: Mapped[int] = pk_column()
    request_id: Mapped[str | None] = mapped_column(String(36), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id", ondelete="SET NULL"))
    operation_type: Mapped[str] = mapped_column(Enum("login", "logout", "single_detection", "batch_detection", "result_query", "report_export", "model_activate", "config_change", name="operation_type"), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(50))
    resource_id: Mapped[int | None] = mapped_column(BigInteger)
    operation_status: Mapped[str] = mapped_column(Enum("success", "failed", name="operation_status"), nullable=False)
    detail_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class ExplanationSnapshot(Base):
    __tablename__ = "explanation_snapshot"

    id: Mapped[int] = pk_column()
    result_id: Mapped[int] = mapped_column(ForeignKey("detection_result.id", ondelete="CASCADE"), unique=True, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ReportMetadata(Base):
    __tablename__ = "report_metadata"

    id: Mapped[int] = pk_column()
    report_no: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    task_id: Mapped[int] = mapped_column(ForeignKey("detection_task.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(Enum("pending", "succeeded", "failed", name="report_status"), nullable=False, default="pending")
    summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
