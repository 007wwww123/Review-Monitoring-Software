"""Create the seven-table lightweight application schema."""
from alembic import op
from app.db.base import Base
from app import models  # noqa: F401

revision = "001_lightweight_core_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(op.get_bind())
