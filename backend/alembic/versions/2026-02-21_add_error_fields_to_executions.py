"""add_error_fields_to_executions

Revision ID: o3p4q5r6s7t8
Revises: i8j9k0l1m2n3
Create Date: 2026-02-21 10:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "o3p4q5r6s7t8"
down_revision: Union[str, Sequence[str], None] = "i8j9k0l1m2n3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add error_type and error_detail columns to executions table."""
    op.add_column(
        "executions",
        sa.Column("error_type", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "executions",
        sa.Column("error_detail", sa.String(length=2000), nullable=True),
    )


def downgrade() -> None:
    """Remove error_type and error_detail columns from executions table."""
    op.drop_column("executions", "error_detail")
    op.drop_column("executions", "error_type")
