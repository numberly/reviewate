"""Add feedbacks and team_guidelines tables for simplified feedback learning.

This migration creates:
- feedbacks table: stores raw user feedback signals
- team_guidelines table: stores summarized guidelines from batch processing

Revision ID: g6h7i8j9k0l1
Revises: e5f6g7h8i9j0
Create Date: 2026-02-03

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g6h7i8j9k0l1"
down_revision: str | None = "e5f6g7h8i9j0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create feedbacks and team_guidelines tables."""
    # Create feedbacks table
    op.create_table(
        "feedbacks",
        # Primary key
        sa.Column("id", sa.UUID(), nullable=False),
        # Ownership
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("repository_id", sa.UUID(), nullable=True),
        # Feedback content
        sa.Column("feedback_type", sa.String(length=50), nullable=False),
        sa.Column("review_comment", sa.Text(), nullable=False),
        sa.Column("user_response", sa.Text(), nullable=True),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        # Metadata
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default="false"),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_feedbacks_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name="fk_feedbacks_repository_id_repositories",
            ondelete="CASCADE",
        ),
    )

    # Create indexes for feedbacks
    op.create_index("ix_feedbacks_id", "feedbacks", ["id"], unique=False)
    op.create_index("ix_feedbacks_organization_id", "feedbacks", ["organization_id"], unique=False)
    op.create_index("ix_feedbacks_repository_id", "feedbacks", ["repository_id"], unique=False)
    op.create_index(
        "ix_feedbacks_org_processed",
        "feedbacks",
        ["organization_id", "processed"],
        unique=False,
    )

    # Create team_guidelines table
    op.create_table(
        "team_guidelines",
        # Primary key
        sa.Column("id", sa.UUID(), nullable=False),
        # Ownership
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("repository_id", sa.UUID(), nullable=True),
        # Guidelines content
        sa.Column("guidelines_text", sa.Text(), nullable=False),
        sa.Column("feedback_count", sa.Integer(), nullable=False, server_default="0"),
        # Timestamps
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_team_guidelines_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name="fk_team_guidelines_repository_id_repositories",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "repository_id",
            name="uq_team_guidelines_org_repo",
        ),
    )

    # Create indexes for team_guidelines
    op.create_index("ix_team_guidelines_id", "team_guidelines", ["id"], unique=False)
    op.create_index(
        "ix_team_guidelines_organization_id",
        "team_guidelines",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_team_guidelines_repository_id",
        "team_guidelines",
        ["repository_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop feedbacks and team_guidelines tables."""
    # Drop team_guidelines indexes and table
    op.drop_index("ix_team_guidelines_repository_id", table_name="team_guidelines")
    op.drop_index("ix_team_guidelines_organization_id", table_name="team_guidelines")
    op.drop_index("ix_team_guidelines_id", table_name="team_guidelines")
    op.drop_table("team_guidelines")

    # Drop feedbacks indexes and table
    op.drop_index("ix_feedbacks_org_processed", table_name="feedbacks")
    op.drop_index("ix_feedbacks_repository_id", table_name="feedbacks")
    op.drop_index("ix_feedbacks_organization_id", table_name="feedbacks")
    op.drop_index("ix_feedbacks_id", table_name="feedbacks")
    op.drop_table("feedbacks")
