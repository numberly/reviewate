# Code Reviewer Environment Variables

Environment variables for running the code reviewer standalone (CLI or container).

## Authentication

Depends on the auth mode chosen during `reviewate config`:

| Variable | Auth Mode | Description |
|----------|-----------|-------------|
| `ANTHROPIC_API_KEY` | API key / Custom | Anthropic API key |
| `CLAUDE_CODE_OAUTH_TOKEN` | Subscription | OAuth token for headless/container use (generate with `claude setup-token`). Locally, the CLI session is used — no env var needed |

## Model Configuration

| Variable | Description |
|----------|-------------|
| `REVIEWATE_REVIEW_MODEL` | Review tier model — AnalyzeAgent, FactCheckAgent (default: `sonnet`) |
| `REVIEWATE_UTILITY_MODEL` | Utility tier model — Synthesizer, Dedup, Style, etc. (default: `haiku`) |
| `REVIEWATE_BASE_URL` | Custom base URL (e.g., LiteLLM proxy at `http://proxy:4000`) |

## Platform Tokens

At least one platform token is required:

| Variable | Description |
|----------|-------------|
| `GITHUB_TOKEN` | GitHub token (also used by `gh` CLI) |
| `GITLAB_TOKEN` | GitLab token (used by `glab` CLI) |

## Self-Hosted Platforms

| Variable | Default | Description |
|----------|---------|-------------|
| `GITLAB_HOST` | `https://gitlab.com` | GitLab self-hosted instance URL |

## Container Mode

| Variable | Description |
|----------|-------------|
| `REVIEWATE_CONTAINER_MODE` | Set to `1` when running in a container |
| `REVIEWATE_DEBUG` | Set to `1` for debug logging |
| `TEAM_GUIDELINES` | Team-specific review guidelines (injected by backend) |
