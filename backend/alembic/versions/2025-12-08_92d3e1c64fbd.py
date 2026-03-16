"""add_head_sha_to_pull_requests

Revision ID: 92d3e1c64fbd
Revises: 9fa82dbfc1d2
Create Date: 2025-12-08 18:06:14.777454

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "92d3e1c64fbd"
down_revision: Union[str, Sequence[str], None] = "9fa82dbfc1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add head_sha column to pull_requests table
    op.add_column(
        "pull_requests",
        sa.Column("head_sha", sa.String(length=40), nullable=False, server_default=""),
    )
    # Remove server default after adding the column
    op.alter_column("pull_requests", "head_sha", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    # Remove head_sha column
    op.drop_column("pull_requests", "head_sha")
