"""Job lease: claim time and attempt count let the sweep recover dead workers."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("jobs") as batch:
        batch.add_column(sa.Column("started_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    with op.batch_alter_table("jobs") as batch:
        batch.drop_column("attempts")
        batch.drop_column("started_at")
