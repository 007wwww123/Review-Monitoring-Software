"""Persist queued batch payloads for the independent GPU worker."""

from alembic import op
from sqlalchemy import BigInteger, Column, DateTime, Enum, ForeignKey, Integer, JSON, String, UniqueConstraint, inspect

revision = "004_batch_task_items"
down_revision = "003_review_time"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "detection_task_item" in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "detection_task_item",
        Column("id", BigInteger, primary_key=True, autoincrement=True),
        Column("task_id", BigInteger, ForeignKey("detection_task.id", ondelete="CASCADE"), nullable=False),
        Column("item_index", Integer, nullable=False),
        Column("request_json", JSON, nullable=False),
        Column("status", Enum("queued", "running", "succeeded", "failed", name="detection_task_item_status"), nullable=False),
        Column("result_id", BigInteger, ForeignKey("detection_result.id", ondelete="SET NULL")),
        Column("error_message", String(1000)),
        Column("started_at", DateTime),
        Column("finished_at", DateTime),
        Column("created_at", DateTime, nullable=False),
        UniqueConstraint("task_id", "item_index", name="uq_task_item_index"),
    )
    op.create_index("ix_detection_task_item_task_id", "detection_task_item", ["task_id"])


def downgrade() -> None:
    if "detection_task_item" in inspect(op.get_bind()).get_table_names():
        op.drop_table("detection_task_item")
