"""change_summary_trigger_default_to_label

Revision ID: u9v0w1x2y3z4
Revises: o3p4q5r6s7t8
Create Date: 2026-02-25 10:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "u9v0w1x2y3z4"
down_revision: Union[str, Sequence[str], None] = "o3p4q5r6s7t8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change default for automatic_summary_trigger from 'none' to 'label'."""
    op.alter_column(
        "organizations",
        "automatic_summary_trigger",
        server_default="label",
    )


def downgrade() -> None:
    """Revert default for automatic_summary_trigger back to 'none'."""
    op.alter_column(
        "organizations",
        "automatic_summary_trigger",
        server_default="none",
    )
