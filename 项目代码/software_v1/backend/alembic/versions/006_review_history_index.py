"""Index leakage-safe user history lookups by user and event time."""

from alembic import op
from sqlalchemy import inspect

revision = "006_review_history_index"
down_revision = "005_evaluation_auc_metrics"
branch_labels = None
depends_on = None


INDEX_NAME = "idx_review_user_time"


def upgrade() -> None:
    indexes = {
        index["name"]
        for index in inspect(op.get_bind()).get_indexes("review_event")
    }
    if INDEX_NAME not in indexes:
        op.create_index(
            INDEX_NAME,
            "review_event",
            ["user_key", "review_time", "id"],
        )


def downgrade() -> None:
    indexes = {
        index["name"]
        for index in inspect(op.get_bind()).get_indexes("review_event")
    }
    if INDEX_NAME in indexes:
        op.drop_index(INDEX_NAME, table_name="review_event")
