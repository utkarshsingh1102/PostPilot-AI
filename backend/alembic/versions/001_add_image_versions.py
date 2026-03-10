"""Add post_image_versions table and reimagine_status column

Revision ID: 001_add_image_versions
Revises:
Create Date: 2026-03-10

"""
from alembic import op
import sqlalchemy as sa

revision = "001_add_image_versions"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add reimagine_status column to processed_posts
    op.add_column(
        "processed_posts",
        sa.Column("reimagine_status", sa.String(), nullable=False, server_default="idle"),
    )

    # Create post_image_versions table
    op.create_table(
        "post_image_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("processed_post_id", sa.Integer(), nullable=False),
        sa.Column("image_path", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["processed_post_id"], ["processed_posts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_post_image_versions_id", "post_image_versions", ["id"])
    op.create_index(
        "ix_post_image_versions_processed_post_id",
        "post_image_versions",
        ["processed_post_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_post_image_versions_processed_post_id", table_name="post_image_versions")
    op.drop_index("ix_post_image_versions_id", table_name="post_image_versions")
    op.drop_table("post_image_versions")
    op.drop_column("processed_posts", "reimagine_status")
