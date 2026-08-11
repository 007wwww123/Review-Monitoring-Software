"""Store PR-AUC and ROC-AUC separately for reproducible evaluation."""

from alembic import op
from sqlalchemy import Column, Numeric, inspect

revision = "005_evaluation_auc_metrics"
down_revision = "004_batch_task_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("evaluation_report")}
    if "pr_auc_score" not in columns:
        op.add_column("evaluation_report", Column("pr_auc_score", Numeric(8, 7)))
    if "roc_auc_score" not in columns:
        op.add_column("evaluation_report", Column("roc_auc_score", Numeric(8, 7)))


def downgrade() -> None:
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("evaluation_report")}
    if "roc_auc_score" in columns:
        op.drop_column("evaluation_report", "roc_auc_score")
    if "pr_auc_score" in columns:
        op.drop_column("evaluation_report", "pr_auc_score")
