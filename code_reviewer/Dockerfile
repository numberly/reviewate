## Builder stage — installs deps, then discarded
FROM python:3.14-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg git && rm -rf /var/lib/apt/lists/*

# GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    -o /usr/share/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
    > /etc/apt/sources.list.d/github-cli.list && \
    apt-get update && apt-get install -y --no-install-recommends gh && rm -rf /var/lib/apt/lists/*

# Gitleaks (secret scanner)
ARG GITLEAKS_VERSION=8.30.0
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "amd64" ]; then ARCH="x64"; fi && \
    curl -fsSL "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_${ARCH}.tar.gz" \
    | tar -xz -C /usr/local/bin gitleaks

# GitLab CLI
ARG GLAB_VERSION=1.88.0
RUN curl -fsSL "https://gitlab.com/gitlab-org/cli/-/releases/v${GLAB_VERSION}/downloads/glab_${GLAB_VERSION}_linux_$(dpkg --print-architecture).deb" \
    -o /tmp/glab.deb && dpkg -i /tmp/glab.deb && rm /tmp/glab.deb

# Python deps
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN useradd -m -u 1000 reviewate
COPY --chown=reviewate:reviewate pyproject.toml uv.lock /app/
RUN cd /app && uv sync --frozen --no-dev --no-install-project


## Runtime stage — only what's needed to run
FROM python:3.14-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates curl unzip && rm -rf /var/lib/apt/lists/*

# Bun + Claude Code CLI (SDK spawns claude-code as subprocess)
ARG BUN_VERSION=1.2.5
RUN DPKG_ARCH=$(dpkg --print-architecture) && \
    case "$DPKG_ARCH" in arm64) BUN_ARCH="aarch64";; amd64) BUN_ARCH="x64";; *) echo "Unsupported arch: $DPKG_ARCH" >&2; exit 1;; esac && \
    curl -fsSL --retry 3 "https://github.com/oven-sh/bun/releases/download/bun-v${BUN_VERSION}/bun-linux-${BUN_ARCH}.zip" \
    -o /tmp/bun.zip && \
    unzip -q /tmp/bun.zip -d /tmp && \
    mv /tmp/bun-linux-${BUN_ARCH}/bun /usr/local/bin/bun && \
    chmod +x /usr/local/bin/bun && \
    rm -rf /tmp/bun.zip /tmp/bun-linux-* && \
    bun install -g @anthropic-ai/claude-code

# Copy CLI tools from builder
COPY --from=builder /usr/bin/gh /usr/bin/gh
COPY --from=builder /usr/local/bin/gitleaks /usr/local/bin/gitleaks
COPY --from=builder /usr/bin/glab /usr/bin/glab

# Non-root user
RUN useradd -m -u 1000 reviewate
USER reviewate
WORKDIR /home/reviewate

# Copy venv from builder
COPY --from=builder --chown=reviewate:reviewate /app/.venv /app/.venv

# Copy source
COPY --chown=reviewate:reviewate . /app/code_reviewer/

# Make `reviewate` available as a command for CI (GitHub Actions, GitLab CI)
# Mirrors the ENTRYPOINT setup since CI runners override the entrypoint
RUN printf '#!/bin/sh\nmkdir -p /tmp/.claude\necho '"'"'{"hasCompletedOnboarding":true}'"'"' > /tmp/.claude.json\nexport HOME=/tmp\nulimit -s unlimited\nexec python /app/code_reviewer/main.py "$@"\n' > /app/.venv/bin/reviewate && chmod +x /app/.venv/bin/reviewate

ENV REVIEWATE_CONTAINER_MODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:/root/.bun/bin:${PATH}" \
    GH_CONFIG_DIR="/tmp/gh" \
    GLAB_CONFIG_DIR="/tmp/glab"

ENTRYPOINT ["sh", "-c", "mkdir -p /tmp/.claude && echo '{\"hasCompletedOnboarding\":true}' > /tmp/.claude.json && export HOME=/tmp && ulimit -s unlimited && exec python /app/code_reviewer/main.py \"$@\"", "--"]
