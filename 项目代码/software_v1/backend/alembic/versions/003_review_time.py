"""Preserve the full review timestamp required by GRU time-gap features."""

from alembic import op
from sqlalchemy import Column, DateTime, inspect, text

revision = "003_review_time"
down_revision = "002_contract_explanation_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("review_event")}
    if "review_time" not in columns:
        op.add_column("review_event", Column("review_time", DateTime, nullable=True))
        op.execute(text("UPDATE review_event SET review_time = review_date WHERE review_date IS NOT NULL"))
        op.create_index("ix_review_event_review_time", "review_event", ["review_time"])


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("review_event")}
    if "review_time" in columns:
        op.drop_index("ix_review_event_review_time", table_name="review_event")
        op.drop_column("review_event", "review_time")
