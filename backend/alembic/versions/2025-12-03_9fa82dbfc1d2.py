"""Add pull_requests table

Revision ID: 9fa82dbfc1d2
Revises: 4854079ed6bc
Create Date: 2025-12-03 11:53:40.739213

"""

from collections.abc import Sequence
from typing import Union
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9fa82dbfc1d2"
down_revision: Union[str, Sequence[str], None] = "4854079ed6bc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Step 1: Create pull_requests table
    op.create_table(
        "pull_requests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("repository_id", sa.UUID(), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("external_pr_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("head_branch", sa.String(length=255), nullable=False),
        sa.Column("base_branch", sa.String(length=255), nullable=False),
        sa.Column("pr_url", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_pull_requests_organization_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name="fk_pull_requests_repository_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repository_id", "pr_number", name="uq_pull_requests_repo_pr"),
    )
    op.create_index(
        op.f("ix_pull_requests_created_at"), "pull_requests", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_pull_requests_external_pr_id"), "pull_requests", ["external_pr_id"], unique=False
    )
    op.create_index(op.f("ix_pull_requests_id"), "pull_requests", ["id"], unique=False)
    op.create_index(
        op.f("ix_pull_requests_organization_id"), "pull_requests", ["organization_id"], unique=False
    )
    op.create_index(
        op.f("ix_pull_requests_pr_number"), "pull_requests", ["pr_number"], unique=False
    )
    op.create_index(
        op.f("ix_pull_requests_repository_id"), "pull_requests", ["repository_id"], unique=False
    )
    op.create_index(op.f("ix_pull_requests_state"), "pull_requests", ["state"], unique=False)

    # Step 2: Add pull_request_id column as NULLABLE (we'll make it NOT NULL after data migration)
    op.add_column("executions", sa.Column("pull_request_id", sa.UUID(), nullable=True))
    op.create_index(
        op.f("ix_executions_pull_request_id"), "executions", ["pull_request_id"], unique=False
    )

    # Step 3: Data migration - create PR records from existing executions
    conn = op.get_bind()

    # Get distinct PRs from executions (grouped by repository + pr_number)
    results = conn.execute(
        text("""
        SELECT DISTINCT
            e.repository_id,
            e.pr_number,
            e.organization_id,
            MIN(e.created_at) as first_created
        FROM executions e
        GROUP BY e.repository_id, e.pr_number, e.organization_id
        ORDER BY first_created ASC
    """)
    )

    for row in results:
        repo_id, pr_num, org_id, created = row

        # Get repository info for URL construction
        repo_result = conn.execute(
            text("""
            SELECT provider, provider_url, name, external_repo_id
            FROM repositories
            WHERE id = :repo_id
        """),
            {"repo_id": str(repo_id)},
        )
        repo = repo_result.fetchone()

        if not repo:
            continue  # Skip if repository doesn't exist

        # Construct PR URL based on provider
        # Note: We use placeholder values since we don't have the actual org/namespace
        provider, provider_url, _repo_name, _external_repo_id = repo
        if provider == "github":
            # GitHub URL format: https://github.com/owner/repo/pull/123
            pr_url = f"{provider_url}/pull/{pr_num}"
        else:  # gitlab
            # GitLab URL format: https://gitlab.com/namespace/project/-/merge_requests/123
            pr_url = f"{provider_url}/-/merge_requests/{pr_num}"

        # Generate new UUID for PR
        pr_id = uuid4()

        # Insert PR record with placeholder data
        conn.execute(
            text("""
            INSERT INTO pull_requests (
                id, organization_id, repository_id, pr_number, external_pr_id,
                title, author, state, head_branch, base_branch, pr_url,
                created_at, updated_at
            ) VALUES (
                :id, :org_id, :repo_id, :pr_num, :external_id,
                :title, :author, :state, :head, :base, :url,
                :created, :updated
            )
        """),
            {
                "id": str(pr_id),
                "org_id": str(org_id),
                "repo_id": str(repo_id),
                "pr_num": pr_num,
                "external_id": f"migration-{repo_id}-{pr_num}",
                "title": f"PR #{pr_num}",
                "author": "unknown",
                "state": "open",
                "head": "unknown",
                "base": "unknown",
                "url": pr_url,
                "created": created,
                "updated": created,
            },
        )
        conn.commit()

        # Update all executions for this PR to link to the new PR record
        conn.execute(
            text("""
            UPDATE executions
            SET pull_request_id = :pr_id
            WHERE repository_id = :repo_id AND pr_number = :pr_num
        """),
            {"pr_id": str(pr_id), "repo_id": str(repo_id), "pr_num": pr_num},
        )
        conn.commit()

    # Step 4: Make pull_request_id NOT NULL (all executions should now have a PR link)
    op.alter_column("executions", "pull_request_id", nullable=False)

    # Step 5: Add foreign key constraint
    op.create_foreign_key(
        "fk_executions_pull_request_id_pull_requests",
        "executions",
        "pull_requests",
        ["pull_request_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(
        "fk_executions_pull_request_id_pull_requests", "executions", type_="foreignkey"
    )
    op.drop_index(op.f("ix_executions_pull_request_id"), table_name="executions")
    op.drop_column("executions", "pull_request_id")
    op.drop_index(op.f("ix_pull_requests_state"), table_name="pull_requests")
    op.drop_index(op.f("ix_pull_requests_repository_id"), table_name="pull_requests")
    op.drop_index(op.f("ix_pull_requests_pr_number"), table_name="pull_requests")
    op.drop_index(op.f("ix_pull_requests_organization_id"), table_name="pull_requests")
    op.drop_index(op.f("ix_pull_requests_id"), table_name="pull_requests")
    op.drop_index(op.f("ix_pull_requests_external_pr_id"), table_name="pull_requests")
    op.drop_index(op.f("ix_pull_requests_created_at"), table_name="pull_requests")
    op.drop_table("pull_requests")
    # ### end Alembic commands ###
