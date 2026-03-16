# Contributing to Reviewate

Thanks for your interest in contributing to Reviewate! This guide will help you get started.

## Getting Started

1. **Fork** the repository
2. **Clone** your fork locally
3. **Install** dependencies (see [Development Setup](#development-setup))
4. **Create a branch** for your changes
5. **Make your changes**, ensuring tests pass
6. **Submit a pull request**

## Development Setup

```bash
# Clone the repository
git clone https://github.com/<your-username>/reviewate.git
cd reviewate

# Install frontend/monorepo dependencies
pnpm install

# Install backend dependencies
cd backend && uv sync && cd ..

# Install code reviewer dependencies
cd code_reviewer && uv sync && cd ..

# Start database for local development
make compose-test

# Run migrations
make migrate

# Start development servers (separate terminals)
make backend-run   # http://localhost:8000
make frontend-run  # http://localhost:3000
```

## Making Changes

### Branch Naming

Use descriptive branch names:

- `feat/add-bitbucket-support`
- `fix/gitlab-webhook-timeout`
- `docs/update-deployment-guide`

### Commit Messages

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add support for Bitbucket webhooks
fix: handle empty diff in review agent
docs: update Kubernetes deployment guide
refactor: simplify container backend interface
test: add fact checker edge case tests
chore: update litellm dependency
```

### Code Style

**Python (backend, code_reviewer):**

- Formatted with [Ruff](https://docs.astral.sh/ruff/)
- Type hints required on all public functions
- Docstrings on public classes and methods

**TypeScript/Vue (frontend, website):**

- Formatted with [Prettier](https://prettier.io/)
- Linted with [ESLint](https://eslint.org/)

### Running Checks

Before submitting a PR, ensure everything passes:

```bash
# Run linting and formatting checks
make qa

# Run all tests
make test

# Or run tests individually
make backend-test
make code-review-test
make frontend-test
```

## Pull Requests

1. Keep PRs focused on a single change
2. Include tests for new features and bug fixes
3. Update documentation if your change affects user-facing behavior
4. Ensure `make qa` and `make test` pass
5. Fill in the PR template

## Project Structure

```
reviewate/
├── backend/          # FastAPI backend (Python)
├── frontend/         # Nuxt dashboard (Vue/TypeScript)
├── code_reviewer/    # AI review engine (Python)
├── packages/         # Shared TypeScript SDK
├── website/          # Marketing site (Nuxt)
└── docs/             # Deployment and configuration docs
```

Each sub-project has its own `CLAUDE.md` with architecture details and development notes.

## Reporting Bugs

Please use the [bug report template](https://github.com/numberly/reviewate/issues/new?template=bug_report.yml) and include:

- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python/Node version, Docker version)
- Relevant logs

## Requesting Features

Use the [feature request template](https://github.com/numberly/reviewate/issues/new?template=feature_request.yml). Describe the problem you're trying to solve, not just the solution you have in mind.

## License

By contributing, you agree that your contributions will be licensed under the [AGPL-3.0 License](LICENSE).
