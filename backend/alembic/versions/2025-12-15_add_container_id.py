"""add_container_id_to_executions

Revision ID: a1b2c3d4e5f6
Revises: 92d3e1c64fbd
Create Date: 2025-12-15 12:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "92d3e1c64fbd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add container_id column to executions table
    op.add_column(
        "executions",
        sa.Column("container_id", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove container_id column
    op.drop_column("executions", "container_id")
