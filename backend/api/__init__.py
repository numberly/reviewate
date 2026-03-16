"""Reviewate API - Core exports.

Note: We intentionally don't import Application here to avoid circular imports
and heavy initialization during alembic migrations. Import directly from api.app
when needed:

    from api.app import Application
    from api.context import get_current_app
"""
