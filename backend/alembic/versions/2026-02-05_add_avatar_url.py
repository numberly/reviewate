"""add_avatar_url_to_organizations_and_repositories

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h9
Create Date: 2026-02-05 12:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6g7h9"
down_revision: Union[str, Sequence[str], None] = "h7i8j9k0l1m2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add avatar_url column to organizations and repositories tables."""
    op.add_column(
        "organizations",
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "repositories",
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    """Remove avatar_url columns."""
    op.drop_column("repositories", "avatar_url")
    op.drop_column("organizations", "avatar_url")
