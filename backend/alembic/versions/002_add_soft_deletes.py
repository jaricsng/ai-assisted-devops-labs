"""Add deleted_at soft-delete column to all domain tables

Revision ID: 002
Revises: 001
Create Date: 2026-06-14

"""

import sqlalchemy as sa

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "projects", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "tasks", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "comments", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
    )

    op.create_index("ix_users_deleted_at", "users", ["deleted_at"])
    op.create_index("ix_projects_deleted_at", "projects", ["deleted_at"])
    op.create_index("ix_tasks_deleted_at", "tasks", ["deleted_at"])
    op.create_index("ix_comments_deleted_at", "comments", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_comments_deleted_at", table_name="comments")
    op.drop_index("ix_tasks_deleted_at", table_name="tasks")
    op.drop_index("ix_projects_deleted_at", table_name="projects")
    op.drop_index("ix_users_deleted_at", table_name="users")

    op.drop_column("comments", "deleted_at")
    op.drop_column("tasks", "deleted_at")
    op.drop_column("projects", "deleted_at")
    op.drop_column("users", "deleted_at")
