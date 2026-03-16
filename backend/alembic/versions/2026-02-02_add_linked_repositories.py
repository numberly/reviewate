"""Add linked_repositories table

Adds linked_repositories table to store repositories that are linked to an
organization or repository for context during code reviews.

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-02-02

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6g7h8i9j0"
down_revision: str | None = "d4e5f6g7h8i9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create linked_repositories table."""
    op.create_table(
        "linked_repositories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=True),
        sa.Column("repository_id", sa.UUID(), nullable=True),
        sa.Column("linked_provider", sa.String(length=20), nullable=False),
        sa.Column("linked_provider_url", sa.String(length=512), nullable=False),
        sa.Column("linked_repo_path", sa.String(length=512), nullable=False),
        sa.Column("linked_branch", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_linked_repositories_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name="fk_linked_repositories_repository_id_repositories",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "linked_repo_path",
            "linked_provider_url",
            name="uq_linked_repo_org",
        ),
        sa.UniqueConstraint(
            "repository_id",
            "linked_repo_path",
            "linked_provider_url",
            name="uq_linked_repo_repo",
        ),
    )
    op.create_index(op.f("ix_linked_repositories_id"), "linked_repositories", ["id"], unique=False)
    op.create_index(
        op.f("ix_linked_repositories_organization_id"),
        "linked_repositories",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_linked_repositories_repository_id"),
        "linked_repositories",
        ["repository_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop linked_repositories table."""
    op.drop_index(op.f("ix_linked_repositories_repository_id"), table_name="linked_repositories")
    op.drop_index(op.f("ix_linked_repositories_organization_id"), table_name="linked_repositories")
    op.drop_index(op.f("ix_linked_repositories_id"), table_name="linked_repositories")
    op.drop_table("linked_repositories")
