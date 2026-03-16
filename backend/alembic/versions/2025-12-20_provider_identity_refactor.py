"""Provider Identity refactor - introduce provider_identities table.

This migration:
1. Creates provider_identities table to store provider-specific identity data
2. Restructures organization_memberships to reference provider_identity_id instead of user_id
3. Adds reviewate_enabled setting to organization_memberships
4. Cleans up users table by removing provider-specific fields and making email nullable

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2025-12-20

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6g7h8i9"
down_revision: str | None = "c3d4e5f6g7h8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the provider identity refactor."""
    # Step 1: Create provider_identities table
    op.create_table(
        "provider_identities",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_provider_identities_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "external_id", name="uq_provider_identity_provider_external_id"
        ),
    )
    op.create_index(op.f("ix_provider_identities_id"), "provider_identities", ["id"], unique=False)
    op.create_index(
        op.f("ix_provider_identities_external_id"),
        "provider_identities",
        ["external_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provider_identities_user_id"), "provider_identities", ["user_id"], unique=False
    )

    # Step 2: Restructure organization_memberships
    # Drop old constraints and indexes first
    op.drop_constraint("organization_memberships_pkey", "organization_memberships", type_="primary")
    op.drop_constraint(
        "fk_organization_memberships_user_id_users", "organization_memberships", type_="foreignkey"
    )

    # Add new columns
    op.add_column(
        "organization_memberships",
        sa.Column("id", sa.UUID(), nullable=False),
    )
    op.add_column(
        "organization_memberships",
        sa.Column("provider_identity_id", sa.UUID(), nullable=False),
    )
    op.add_column(
        "organization_memberships",
        sa.Column("reviewate_enabled", sa.Boolean(), nullable=False, server_default="true"),
    )

    # Drop user_id column (clean db, no data to migrate)
    op.drop_column("organization_memberships", "user_id")

    # Add new primary key on id
    op.create_primary_key("organization_memberships_pkey", "organization_memberships", ["id"])

    # Add foreign key to provider_identities
    op.create_foreign_key(
        "fk_organization_memberships_provider_identity_id",
        "organization_memberships",
        "provider_identities",
        ["provider_identity_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Add unique constraint
    op.create_unique_constraint(
        "uq_org_membership_org_identity",
        "organization_memberships",
        ["organization_id", "provider_identity_id"],
    )

    # Add indexes
    op.create_index(
        op.f("ix_organization_memberships_id"), "organization_memberships", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_organization_memberships_organization_id"),
        "organization_memberships",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_organization_memberships_provider_identity_id"),
        "organization_memberships",
        ["provider_identity_id"],
        unique=False,
    )

    # Step 3: Clean up users table
    # Drop indexes on external_id columns
    op.drop_index("ix_users_github_external_id", table_name="users")
    op.drop_index("ix_users_gitlab_external_id", table_name="users")
    op.drop_index("ix_users_google_external_id", table_name="users")

    # Drop provider columns
    op.drop_column("users", "github_external_id")
    op.drop_column("users", "gitlab_external_id")
    op.drop_column("users", "google_external_id")
    op.drop_column("users", "github_username")
    op.drop_column("users", "gitlab_username")

    # Make email nullable
    op.alter_column("users", "email", nullable=True)


def downgrade() -> None:
    """Revert the provider identity refactor."""
    # Step 1: Restore users table structure
    op.alter_column("users", "email", nullable=False)

    op.add_column(
        "users",
        sa.Column("github_external_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("gitlab_external_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("google_external_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("github_username", sa.String(255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("gitlab_username", sa.String(255), nullable=True),
    )

    # Restore indexes
    op.create_index("ix_users_github_external_id", "users", ["github_external_id"], unique=True)
    op.create_index("ix_users_gitlab_external_id", "users", ["gitlab_external_id"], unique=True)
    op.create_index("ix_users_google_external_id", "users", ["google_external_id"], unique=True)

    # Step 2: Restore organization_memberships structure
    # Drop new constraints and indexes
    op.drop_index(
        "ix_organization_memberships_provider_identity_id", table_name="organization_memberships"
    )
    op.drop_index(
        "ix_organization_memberships_organization_id", table_name="organization_memberships"
    )
    op.drop_index("ix_organization_memberships_id", table_name="organization_memberships")
    op.drop_constraint("uq_org_membership_org_identity", "organization_memberships", type_="unique")
    op.drop_constraint(
        "fk_organization_memberships_provider_identity_id",
        "organization_memberships",
        type_="foreignkey",
    )

    # Drop new primary key
    op.drop_constraint("organization_memberships_pkey", "organization_memberships", type_="primary")

    # Add back user_id column
    op.add_column(
        "organization_memberships",
        sa.Column("user_id", sa.UUID(), nullable=False),
    )

    # Add back composite primary key
    op.create_primary_key(
        "organization_memberships_pkey", "organization_memberships", ["user_id", "organization_id"]
    )

    # Add back user_id foreign key
    op.create_foreign_key(
        "fk_organization_memberships_user_id_users",
        "organization_memberships",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Drop new columns
    op.drop_column("organization_memberships", "reviewate_enabled")
    op.drop_column("organization_memberships", "provider_identity_id")
    op.drop_column("organization_memberships", "id")

    # Step 3: Drop provider_identities table
    op.drop_index("ix_provider_identities_user_id", table_name="provider_identities")
    op.drop_index("ix_provider_identities_external_id", table_name="provider_identities")
    op.drop_index("ix_provider_identities_id", table_name="provider_identities")
    op.drop_table("provider_identities")
