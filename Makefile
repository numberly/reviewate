# Quality assurance - runs pre-commit checks
qa:
	uv tool run pre-commit run --all-files

# Run Rust tests for code-reviewer
code-review-test:
	cd code_reviewer && uv run pytest

# Run backend API tests
backend-test:
	cd backend && uv run pytest -v

# Run frontend tests
frontend-test:
	cd frontend && pnpm test:run

# Run all tests
test: code-review-test backend-test frontend-test

# ==================== Development ====================
backend-run: ## Run backend API server locally (requires make compose-test)
	@if [ ! -f .env ]; then echo "Error: .env file not found. Copy .env.example to .env"; exit 1; fi
	@set -a && . ./.env && set +a && cd backend && \
		DATABASE_URL="postgresql://$${POSTGRES_USER}:$${POSTGRES_PASSWORD}@localhost:5432/$${POSTGRES_DB}" \
		REDIS_URL="redis://localhost:6379/0" \
		DOCKER_HOST="tcp://localhost:2375" \
		REVIEWATE_CONFIG="configs/docker.yaml" \
		uv run watchfiles "python run.py" api configs

frontend-run: ## Run frontend dev server locally
	@if [ ! -f .env ]; then echo "Error: .env file not found. Copy .env.example to .env"; exit 1; fi
	@set -a && . ./.env && set +a && cd frontend && pnpm dev

website-dev: ## Run website dev server
	cd website && pnpm dev

website-build: ## Build website for production
	cd website && pnpm generate

compose-all: ## Start all services (Postgres, Redis, backend, frontend)
	docker compose --profile all down -v --remove-orphans && \
	docker compose --profile all up --build

compose-app: ## Start app only (bring your own Postgres/Redis)
	docker compose --profile app down -v --remove-orphans && \
	docker compose --profile app up --build

compose-test: ## Start database only (for local dev/testing)
	docker compose --profile test down -v --remove-orphans && \
	docker compose --profile test up --build

# ==================== Docker Build ====================
REGISTRY ?= reviewate
VERSION ?= 1.1.0 # x-release-please-version

backend-build: ## Build backend Docker image
	docker build --platform linux/amd64 -t $(REGISTRY)/backend:$(VERSION) ./backend

frontend-build: ## Build frontend Docker image
	docker build --platform linux/amd64 -t $(REGISTRY)/frontend:$(VERSION) -f frontend/Dockerfile .

code-reviewer-build: ## Build code-reviewer Docker image
	docker build --platform linux/amd64 -t $(REGISTRY)/code-reviewer:$(VERSION) ./code_reviewer

build: backend-build frontend-build code-reviewer-build ## Build all Docker images

push: build ## Build and push all Docker images (versioned + latest)
	docker tag $(REGISTRY)/backend:$(VERSION) $(REGISTRY)/backend:latest
	docker tag $(REGISTRY)/frontend:$(VERSION) $(REGISTRY)/frontend:latest
	docker tag $(REGISTRY)/code-reviewer:$(VERSION) $(REGISTRY)/code-reviewer:latest
	docker push $(REGISTRY)/backend:$(VERSION)
	docker push $(REGISTRY)/backend:latest
	docker push $(REGISTRY)/frontend:$(VERSION)
	docker push $(REGISTRY)/frontend:latest
	docker push $(REGISTRY)/code-reviewer:$(VERSION)
	docker push $(REGISTRY)/code-reviewer:latest

# ==================== PyPI ====================
publish: ## Build and publish code-reviewer to PyPI
	cd code_reviewer && rm -rf dist && uv build && uv publish

# ==================== Database ====================
migrate: ## Run database migrations
	cd backend && uv run alembic upgrade head

# ==================== Code Generation ====================
generate-types: ## Generate TypeScript types from OpenAPI
	@cd backend && uv run python generate_openapi.py
	@pnpm exec openapi-ts --input $(CURDIR)/packages/api-types/openapi.json --output $(CURDIR)/packages/api-types --client @hey-api/client-fetch
	@echo "export { client } from './client.gen';" >> packages/api-types/index.ts
	@printf '{\n  "name": "@reviewate/api-types",\n  "version": "0.0.1",\n  "type": "module",\n  "main": "./index.ts",\n  "types": "./index.ts",\n  "exports": {\n    ".": "./index.ts",\n    "./client": "./client.gen.ts"\n  },\n  "devDependencies": {\n    "@hey-api/openapi-ts": "^0.88.0"\n  }\n}\n' > packages/api-types/package.json
	@rm -f packages/api-types/openapi.json
	@echo "✅ SDK generated in packages/api-types/"

# ==================== Help ====================
help: ## Show this help
	@echo "Reviewate - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
