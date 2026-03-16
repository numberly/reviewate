# Multi-stage Dockerfile for Reviewate Backend (FastAPI + Python 3.14)

# ===========================
# Stage 1: Builder
# ===========================
FROM python:3.14-slim AS builder

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package installer)
RUN pip install --no-cache-dir uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install Python dependencies
RUN uv pip install --system --no-cache -e .

# ===========================
# Stage 2: Runtime
# ===========================
FROM python:3.14-slim AS runtime

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
# Create docker group for socket access (GID will be overridden by group_add in compose)
RUN groupadd -g 999 docker && \
    useradd -m -u 1000 -G docker reviewate

# Set working directory
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code (world-readable for k8s security context compatibility)
COPY . .
RUN chmod -R a+rX /app

# Create necessary directories
RUN mkdir -p /etc/reviewate-certs && \
    chown -R reviewate:reviewate /etc/reviewate-certs

# Switch to non-root user
USER reviewate

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start server directly (packages installed system-wide via uv)
CMD ["python", "run.py"]
