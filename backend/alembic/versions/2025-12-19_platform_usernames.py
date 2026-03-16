"""Add platform-specific usernames to users table.

Replace single username column with github_username and gitlab_username.

Revision ID: a1b2c3d4e5f6
Revises: 2025-12-18_add_settings_fields
Create Date: 2025-12-19

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6g7h8"
down_revision: str | None = "b2c3d4e5f6g7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add github_username and gitlab_username, migrate data, drop username."""
    # Add new columns
    op.add_column(
        "users",
        sa.Column("github_username", sa.String(255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("gitlab_username", sa.String(255), nullable=True),
    )

    # Migrate existing data: copy username to appropriate platform column based on external_id
    op.execute("""
        UPDATE users
        SET github_username = username
        WHERE github_external_id IS NOT NULL
    """)
    op.execute("""
        UPDATE users
        SET gitlab_username = username
        WHERE gitlab_external_id IS NOT NULL AND github_external_id IS NULL
    """)

    # Drop the old username column
    op.drop_column("users", "username")


def downgrade() -> None:
    """Restore username column from platform-specific columns."""
    # Add back the username column
    op.add_column(
        "users",
        sa.Column("username", sa.String(255), nullable=True),
    )

    # Migrate data back: prefer github_username, fall back to gitlab_username
    op.execute("""
        UPDATE users
        SET username = COALESCE(github_username, gitlab_username, split_part(email, '@', 1))
    """)

    # Make username not nullable
    op.alter_column("users", "username", nullable=False)

    # Drop the new columns
    op.drop_column("users", "github_username")
    op.drop_column("users", "gitlab_username")
