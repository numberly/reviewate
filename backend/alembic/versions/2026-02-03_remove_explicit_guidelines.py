"""Remove explicit guidelines columns from organizations and repositories.

Guidelines are now managed via:
1. CLAUDE.md files in repositories (explicit, user-defined)
2. TeamGuidelines table (implicit, auto-learned from feedback)

Revision ID: h7i8j9k0l1m2
Revises: g6h7i8j9k0l1
Create Date: 2026-02-03
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "h7i8j9k0l1m2"
down_revision = "g6h7i8j9k0l1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove guidelines columns from organizations and repositories."""
    op.drop_column("organizations", "guidelines")
    op.drop_column("repositories", "guidelines")


def downgrade() -> None:
    """Re-add guidelines columns."""
    import sqlalchemy as sa

    op.add_column(
        "organizations",
        sa.Column("guidelines", sa.Text(), nullable=True),
    )
    op.add_column(
        "repositories",
        sa.Column("guidelines", sa.Text(), nullable=True),
    )
