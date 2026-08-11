"""Add versioned explanation snapshots and report metadata.

The repository's original lightweight migration used ``metadata.create_all``.
This revision is conditional so existing installations can upgrade safely while
fresh installations remain compatible with that migration.
"""
from alembic import op
from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, JSON, MetaData, String, inspect

revision = "002_contract_explanation_reports"
down_revision = "001_lightweight_core_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(inspect(bind).get_table_names())
    if "explanation_snapshot" not in existing:
        op.create_table(
            "explanation_snapshot",
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("result_id", Integer, ForeignKey("detection_result.id", ondelete="CASCADE"), nullable=False, unique=True),
            Column("schema_version", String(32), nullable=False),
            Column("payload", JSON, nullable=False),
            Column("created_at", DateTime, nullable=False),
        )
    if "report_metadata" not in existing:
        op.create_table(
            "report_metadata",
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("report_no", String(36), nullable=False, unique=True),
            Column("task_id", Integer, ForeignKey("detection_task.id", ondelete="CASCADE"), nullable=False),
            Column("status", Enum("pending", "succeeded", "failed", name="report_status"), nullable=False),
            Column("summary", JSON, nullable=False),
            Column("created_at", DateTime, nullable=False),
        )


def downgrade() -> None:
    bind = op.get_bind()
    existing = set(inspect(bind).get_table_names())
    if "report_metadata" in existing:
        op.drop_table("report_metadata")
    if "explanation_snapshot" in existing:
        op.drop_table("explanation_snapshot")
