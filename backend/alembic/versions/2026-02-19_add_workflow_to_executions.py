"""add_workflow_to_executions

Revision ID: i8j9k0l1m2n3
Revises: f5g6h7i8j9k0
Create Date: 2026-02-19 10:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "i8j9k0l1m2n3"
down_revision: Union[str, Sequence[str], None] = "f5g6h7i8j9k0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add workflow column to executions table."""
    op.add_column(
        "executions",
        sa.Column(
            "workflow",
            sa.String(length=20),
            nullable=False,
            server_default="review",
        ),
    )


def downgrade() -> None:
    """Remove workflow column from executions table."""
    op.drop_column("executions", "workflow")
