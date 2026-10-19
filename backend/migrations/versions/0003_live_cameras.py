"""Live cameras: sites, cameras and the alerts they raise."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sites",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
    )
    op.create_table(
        "cameras",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("site_id", sa.String(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("zone", sa.JSON()),
        sa.Column("labels", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("site_id", "name", name="uq_site_camera"),
    )
    op.create_table(
        "alerts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("camera_id", sa.String(), sa.ForeignKey("cameras.id"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot_key", sa.String(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
    )


def downgrade():
    op.drop_table("alerts")
    op.drop_table("cameras")
    op.drop_table("sites")
