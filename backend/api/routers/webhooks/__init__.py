"""Webhooks router package.

Combines GitHub and GitLab webhook routers under the /webhooks prefix.
"""

from fastapi import APIRouter

from .github import router as github_router
from .gitlab import router as gitlab_router

# Create main webhooks router
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

# Include sub-routers
router.include_router(github_router)
router.include_router(gitlab_router)

__all__ = ["router"]
