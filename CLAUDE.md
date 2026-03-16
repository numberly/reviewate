# Reviewate

AI-powered code review agent for GitHub and GitLab. Open source.

## Monorepo Structure

- `backend/` - FastAPI backend with plugin architecture
- `frontend/` - Nuxt 3 frontend
- `code_reviewer/` - Python code review agent
- `website/` - Marketing & landing page (Nuxt 4)
- `packages/` - Shared packages (api-types)

## Make Commands

- `make qa` - Run pre-commit checks (linting, formatting)
- `make test` - Run all tests (backend, frontend, code-reviewer)
- `make backend-test` - Run backend tests only
- `make frontend-test` - Run frontend tests only
- `make generate-types` - Generate TypeScript SDK from OpenAPI

## Local Development Tools

- **pgweb** - Database UI at http://localhost:8081
  - Query API: `curl -s "http://localhost:8081/api/query?query=<URL_ENCODED_SQL>"`
  - Example: `curl -s "http://localhost:8081/api/query?query=SELECT%20*%20FROM%20users%20LIMIT%205%3B"`
- **Backend** - FastAPI at http://localhost:8000
- **Frontend** - Nuxt at http://localhost:3000

## Sub-documentation

- [Backend](./backend/CLAUDE.md)
- [Frontend](./frontend/CLAUDE.md)
- [Code Reviewer](./code_reviewer/CLAUDE.md)
- [Website](./website/CLAUDE.md)
