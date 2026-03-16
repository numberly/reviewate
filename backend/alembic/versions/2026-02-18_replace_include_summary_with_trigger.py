"""replace_include_summary_with_automatic_summary_trigger

Revision ID: e4f5g6h7i8j9
Revises: c3d4e5f6g7h9
Create Date: 2026-02-18 12:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4f5g6h7i8j9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6g7h9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Replace include_summary with automatic_summary_trigger."""
    # Add automatic_summary_trigger to organizations (NOT NULL, default "never")
    op.add_column(
        "organizations",
        sa.Column(
            "automatic_summary_trigger",
            sa.String(length=20),
            nullable=False,
            server_default="never",
        ),
    )
    # Add automatic_summary_trigger to repositories (nullable, for inheritance)
    op.add_column(
        "repositories",
        sa.Column("automatic_summary_trigger", sa.String(length=20), nullable=True),
    )
    # Drop include_summary from both tables
    op.drop_column("organizations", "include_summary")
    op.drop_column("repositories", "include_summary")


def downgrade() -> None:
    """Restore include_summary columns."""
    op.add_column(
        "organizations",
        sa.Column("include_summary", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "repositories",
        sa.Column("include_summary", sa.Boolean(), nullable=True),
    )
    op.drop_column("repositories", "automatic_summary_trigger")
    op.drop_column("organizations", "automatic_summary_trigger")
