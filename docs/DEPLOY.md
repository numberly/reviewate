# Deployment Guide

This guide covers deploying the Reviewate platform (backend, frontend, database).

For environment variables reference, see [environment-variables.md](environment-variables.md).

## Deployment Options

| Option | Best For |
|--------|----------|
| [Docker Compose](#docker-compose) | Small teams, single-server deployment |
| [Kubernetes](#kubernetes) | Production, enterprise, high availability |
| [CI Integration](#ci-integration) | Serverless — no dashboard, runs in your pipeline |

---

## Docker Compose

The simplest way to deploy Reviewate. Ideal for small teams and single-server deployments.

### Profiles

| Profile | Services | Use Case |
|---------|----------|----------|
| `all` | postgres, redis, migrate, backend, frontend | Full stack — includes PostgreSQL and Redis. Use when you don't have existing databases |
| `app` | migrate, backend, frontend | Backend + frontend only. Use when you already have PostgreSQL and Redis running |
| `test` | postgres, migrate | PostgreSQL only. For contributors running tests locally |

```bash
# Full stack (recommended)
docker compose --profile all up -d

# App only - set DATABASE_URL and REDIS_URL in .env first
docker compose --profile app up -d

# Database only (for local dev/tests)
docker compose --profile test up -d
```

### Backend Configuration

Two config files are provided in `backend/configs/`:

| Config | Container Backend | Use Case |
|--------|-------------------|----------|
| `docker.yaml` | Docker | Docker Compose (default) |
| `kubernetes.yaml` | Kubernetes | Kubernetes deployment |

Docker Compose uses `docker.yaml` by default.

### External PostgreSQL/Redis

If you already have managed PostgreSQL and Redis (RDS, Cloud SQL, Elasticache, etc.):

```bash
# .env
DATABASE_URL=postgresql://user:pass@your-postgres:5432/reviewate
REDIS_URL=redis://your-redis:6379/0

# Deploy app only (no bundled postgres/redis)
docker compose --profile app up -d
```

### Reverse Proxy

For production with a custom domain, configure your reverse proxy and update `.env`:

```bash
# .env
DOMAIN=reviewate.example.com
FRONTEND_URL=https://reviewate.example.com
NUXT_PUBLIC_API_BASE_URL=https://reviewate.example.com/api
```

Use your preferred reverse proxy (Traefik, Caddy, nginx). See the `nginx/` folder in the repository for an example configuration.

### Updating

```bash
git pull
docker compose --profile all up -d --build
```

This rebuilds images with the latest code and restarts services. Database migrations run automatically on startup.

---

## Kubernetes

Kubernetes deployment gives you high availability, scalability, and stronger isolation for code review jobs. The backend creates Kubernetes Jobs for each review, which are automatically cleaned up after completion.

### Prerequisites

- Kubernetes cluster (1.25+)
- `kubectl` configured
- Container registry access for Reviewate images

### Architecture

```text
┌──────────────────────────────────────────────────────────┐
│                   Kubernetes Cluster                     │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────┐  ┌─────────────┐                        │
│  │   Backend   │  │  Frontend   │                        │
│  └──────┬──────┘  └─────────────┘                        │
│         │                                                │
│         │ creates Jobs via K8s API                       │
│         ▼                                                │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Review Jobs (batch/v1 Jobs)                       │  │
│  │  - Hardened security context (non-root, read-only) │  │
│  │  - Resource limits enforced                        │  │
│  │  - Automatically cleaned up after completion       │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

> **Tip:** For stronger isolation, run review jobs in a **separate namespace** with a NetworkPolicy that denies all ingress from other namespaces. This prevents review containers from communicating with your main services.

### Configuration

Configure your deployment using your preferred method (Helm, Kustomize, raw manifests, etc.). For environment variables and secrets, use whatever fits your infrastructure — External Secrets, Vault, sealed-secrets, or plain Kubernetes secrets.

See [environment-variables.md](environment-variables.md) for all configuration options.

### RBAC and ServiceAccount

The backend needs permissions to create and manage Kubernetes Jobs for code review. Each review creates a Job (with an ephemeral Secret for env vars), watches it to completion, then reads the pod logs for results.

Create a ServiceAccount, Role, and RoleBinding:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: reviewate-backend
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: reviewate-backend
rules:
  # List pods belonging to a Job, read their logs for results
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["list"]
  - apiGroups: [""]
    resources: ["pods/log"]
    verbs: ["get"]
  # Create, watch, and clean up review Jobs
  - apiGroups: ["batch"]
    resources: ["jobs"]
    verbs: ["create", "get", "list", "watch", "delete"]
  # Create ephemeral Secrets with job env vars, patch ownerReferences for cleanup
  - apiGroups: [""]
    resources: ["secrets"]
    verbs: ["create", "get", "list", "patch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: reviewate-backend
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: reviewate-backend
subjects:
  - kind: ServiceAccount
    name: reviewate-backend
```

Review job containers themselves need **no RBAC permissions** — they only need network access to the LLM API and the platform API (GitHub/GitLab).

### Job Security Context

Review Jobs are created with a hardened security context. These settings are not configurable — they are the secure defaults required by most clusters (including those running Kyverno or Pod Security Admission):

- `runAsNonRoot: true`
- `runAsUser: 1000` / `runAsGroup: 1000` (configurable)
- `readOnlyRootFilesystem: true`
- `allowPrivilegeEscalation: false`
- `/tmp` mounted as `emptyDir` (512Mi) for scratch space (cloning repos)

### Reviewate-Specific Configuration

The backend needs to know which namespace and service account to use for spawning review Jobs:

```bash
# Tell the backend to use the Kubernetes container backend
REVIEWATE_CONFIG=/app/configs/kubernetes.yaml

# Namespace and service account for review Jobs
KUBE_NAMESPACE=your-namespace
KUBE_SERVICE_ACCOUNT=reviewate-backend
```

Deploy the backend (`reviewate/backend:latest`) and frontend (`reviewate/frontend:latest`) images using your standard Kubernetes deployment method. The backend listens on port 8000, the frontend on port 3000.

The backend health endpoint is at `/health` (use for liveness/readiness probes).

### Job Isolation (Optional)

For stronger isolation, create a separate namespace for review jobs with a NetworkPolicy:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: reviewate-jobs
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-all-ingress
  namespace: reviewate-jobs
spec:
  podSelector: {}
  policyTypes:
    - Ingress
  ingress: []
```

Configure the backend to use this namespace:

```bash
KUBE_NAMESPACE=reviewate-jobs
KUBE_SERVICE_ACCOUNT=reviewate
```

---

## CI Integration

Run Reviewate as part of your CI pipeline — no server or dashboard needed. Reviews run on every pull request and post comments directly.

> **Note:** CI pipelines and Docker containers **require API tokens** (`GITHUB_API_TOKEN` / `GITLAB_API_TOKEN`). The CLI fallback (`gh` / `glab`) is only available when running locally.

### GitHub Actions

```yaml
# .github/workflows/ai-review.yml
name: AI Code Review
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    container:
      image: reviewate/code-reviewer:latest
    steps:
      - name: Run AI Review
        env:
          GITHUB_API_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          REVIEW_AGENT_MODEL: claude-sonnet-4-6
          REVIEW_AGENT_PROVIDER: anthropic
          UTILITY_AGENT_MODEL: claude-haiku-4-5-20251001
          UTILITY_AGENT_PROVIDER: anthropic
        run: |
          python main.py ${{ github.repository }} \
            -p ${{ github.event.pull_request.number }}
```

**Required secrets:** Set `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`, `GEMINI_API_KEY`) in your repository secrets. `GITHUB_TOKEN` is automatically provided by GitHub Actions.

### GitLab CI

```yaml
ai-review:
  stage: test
  image: reviewate/code-reviewer:latest
  script:
    - python main.py $CI_PROJECT_PATH
        -p $CI_MERGE_REQUEST_IID
        --platform gitlab
  variables:
    GITLAB_API_TOKEN: $GITLAB_API_TOKEN
    ANTHROPIC_API_KEY: $ANTHROPIC_API_KEY
    REVIEW_AGENT_MODEL: claude-sonnet-4-6
    REVIEW_AGENT_PROVIDER: anthropic
    UTILITY_AGENT_MODEL: claude-haiku-4-5-20251001
    UTILITY_AGENT_PROVIDER: anthropic
  only:
    - merge_requests
```

**Required CI/CD variables:** Set `GITLAB_API_TOKEN` (with `api` scope) and `ANTHROPIC_API_KEY` in **Settings > CI/CD > Variables**.

### CLI Options

```bash
python main.py owner/repo -p 123                    # review (default)
python main.py summary owner/repo -p 123            # summary only
python main.py full owner/repo -p 123               # review + summary
```

| Flag | Description |
|------|-------------|
| `-p` / `--pr` | Pull request / merge request number |
| `--platform` | `github` (default) or `gitlab` |
| `--dry-run` | Run without posting comments to the platform |
| `--debug` | Enable debug mode with tracebacks and reasoning output |

### Model Configuration

Set the model and provider for each agent tier via environment variables:

| Variable | Description |
|----------|-------------|
| `REVIEW_AGENT_MODEL` | Model for review agents and fact checker |
| `REVIEW_AGENT_PROVIDER` | Provider for review tier (`anthropic`, `openai`, `gemini`, `openrouter`) |
| `UTILITY_AGENT_MODEL` | Model for triage, style, deduplication |
| `UTILITY_AGENT_PROVIDER` | Provider for utility tier |

#### Provider Examples

```yaml
# Anthropic
REVIEW_AGENT_MODEL: claude-sonnet-4-6
REVIEW_AGENT_PROVIDER: anthropic
UTILITY_AGENT_MODEL: claude-haiku-4-5-20251001
UTILITY_AGENT_PROVIDER: anthropic

# Google Gemini
REVIEW_AGENT_MODEL: gemini-3-flash-preview
REVIEW_AGENT_PROVIDER: gemini
UTILITY_AGENT_MODEL: gemini-2.5-flash-lite
UTILITY_AGENT_PROVIDER: gemini

# OpenAI
REVIEW_AGENT_MODEL: gpt-5.2
REVIEW_AGENT_PROVIDER: openai
UTILITY_AGENT_MODEL: gpt-5-mini
UTILITY_AGENT_PROVIDER: openai
```
