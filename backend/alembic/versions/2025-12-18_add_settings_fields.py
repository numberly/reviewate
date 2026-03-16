"""add_settings_to_organizations_and_repositories

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2025-12-18 12:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6g7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add settings columns to organizations and repositories."""
    # Organization settings (with defaults for existing rows)
    op.add_column(
        "organizations",
        sa.Column("guidelines", sa.Text(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "automatic_review_trigger",
            sa.String(length=20),
            nullable=False,
            server_default="none",
        ),
    )
    op.add_column(
        "organizations",
        sa.Column("include_summary", sa.Boolean(), nullable=False, server_default="true"),
    )
    # Remove server defaults after adding columns (keep model defaults only)
    op.alter_column("organizations", "automatic_review_trigger", server_default=None)
    op.alter_column("organizations", "include_summary", server_default=None)

    # Repository settings (all nullable for inheritance from organization)
    op.add_column(
        "repositories",
        sa.Column("guidelines", sa.Text(), nullable=True),
    )
    op.add_column(
        "repositories",
        sa.Column("automatic_review_trigger", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "repositories",
        sa.Column("include_summary", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    """Remove settings columns."""
    # Repository columns
    op.drop_column("repositories", "include_summary")
    op.drop_column("repositories", "automatic_review_trigger")
    op.drop_column("repositories", "guidelines")

    # Organization columns
    op.drop_column("organizations", "include_summary")
    op.drop_column("organizations", "automatic_review_trigger")
    op.drop_column("organizations", "guidelines")
