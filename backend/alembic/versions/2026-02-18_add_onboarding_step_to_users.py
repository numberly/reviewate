"""add_onboarding_step_to_users

Revision ID: f5g6h7i8j9k0
Revises: e4f5g6h7i8j9
Create Date: 2026-02-18 14:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f5g6h7i8j9k0"
down_revision: Union[str, Sequence[str], None] = "e4f5g6h7i8j9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add onboarding_step column to users table."""
    op.add_column(
        "users",
        sa.Column("onboarding_step", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """Remove onboarding_step column."""
    op.drop_column("users", "onboarding_step")
