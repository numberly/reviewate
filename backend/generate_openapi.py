"""Generate OpenAPI schema for TypeScript type generation."""

import json
from pathlib import Path

from fastapi import FastAPI

from api.routers import (
    auth,
    config,
    linked_repositories,
    organizations,
    pull_requests,
    repositories,
    sources,
    webhooks,
)

# Create minimal FastAPI app
app = FastAPI(
    title="Reviewate API",
    version="1.0.0",
    description="AI-powered code review automation",
)

# Register all routers
app.include_router(auth.router)
app.include_router(config.router)
app.include_router(linked_repositories.router)
app.include_router(organizations.router)
app.include_router(repositories.router)
app.include_router(pull_requests.router)
app.include_router(sources.router)
app.include_router(webhooks.router)

# Generate and save OpenAPI schema
if __name__ == "__main__":
    with Path("../packages/api-types/openapi.json").open("w") as f:
        json.dump(app.openapi(), f, indent=2)
    print("✅ OpenAPI schema generated: packages/api-types/openapi.json")
