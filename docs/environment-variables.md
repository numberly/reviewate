# Backend Environment Variables

Environment variables for deploying the Reviewate backend.

> **Note:** The backend passes LLM configuration to code reviewer containers. See also [Code Reviewer Environment Variables](../code_reviewer/docs/environment-variables.md) for standalone deployment.

## Core Infrastructure

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string (e.g., `postgresql://user:pass@localhost:5432/reviewate`) |
| `ENCRYPTION_KEY` | AES-256-GCM key for encrypting sensitive data. Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `JWT_SECRET_KEY` | Secret key for JWT tokens. Generate with: `openssl rand -hex 32` |
| `REDIS_URL` | Redis connection URL (default: `redis://localhost:6379`) |
| `REDIS_DB` | Redis database number |
| `FRONTEND_URL` | Frontend URL for redirects and CORS (default: `http://localhost:3000`) |

## Plugin Enablement

| Variable | Default | Description |
|----------|---------|-------------|
| `GITHUB_ENABLED` | `true` | Enable GitHub OAuth and integration |
| `GITLAB_ENABLED` | `true` | Enable GitLab OAuth and integration |
| `GOOGLE_ENABLED` | `true` | Enable Google OAuth |

## GitHub Integration

| Variable | Description |
|----------|-------------|
| `GITHUB_CLIENT_ID` | GitHub App client ID |
| `GITHUB_CLIENT_SECRET` | GitHub App client secret |
| `GITHUB_APP_ID` | GitHub App ID |
| `GITHUB_APP_NAME` | GitHub App name |
| `GITHUB_APP_PRIVATE_KEY_PATH` | Path to GitHub App private key (`.pem` file) |
| `GITHUB_WEBHOOK_SECRET` | Secret for verifying GitHub webhooks |

## GitLab Integration

| Variable | Description |
|----------|-------------|
| `GITLAB_CLIENT_ID` | GitLab OAuth application ID |
| `GITLAB_CLIENT_SECRET` | GitLab OAuth application secret |
| `GITLAB_WEBHOOK_SECRET` | Secret for verifying GitLab webhooks |

## Google OAuth

| Variable | Description |
|----------|-------------|
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |

## Self-Hosted Platforms

| Variable | Default | Description |
|----------|---------|-------------|
| `GITHUB_API_URL` | `https://api.github.com` | GitHub Enterprise API URL |
| `GITHUB_AUTHORIZE_URL` | `https://github.com/login/oauth/authorize` | OAuth authorization URL |
| `GITHUB_TOKEN_URL` | `https://github.com/login/oauth/access_token` | OAuth token URL |
| `GITLAB_INSTANCE_URL` | `https://gitlab.com` | GitLab instance URL |
| `GITLAB_API_URL` | `{instance_url}/api/v4` | GitLab API URL |

## Kubernetes Container Backend

| Variable | Default | Description |
|----------|---------|-------------|
| `KUBE_NAMESPACE` | `reviewate` | Namespace for code reviewer jobs |
| `KUBE_SERVICE_ACCOUNT` | `reviewate` | Service account for reviewer pods |
| `KUBE_CLEANUP_JOBS` | `true` | Delete completed Kubernetes jobs |
| `KUBE_TMP_SIZE_LIMIT` | `1Gi` | Size limit for `/tmp` emptyDir volume (scratch space for repo cloning) |

## Development

| Variable | Default | Description |
|----------|---------|-------------|
| `REVIEWATE_CONFIG` | `configs/api.yaml` | Path to config file |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `ENVIRONMENT` | `development` | Environment name |
