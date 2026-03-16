# ADR-004: Pluggable Container Backend Architecture

**Status**: Accepted
**Date**: 2025-01-29

## Context

Reviewate executes code reviews in isolated containers. Different deployment environments require different container runtimes:

- **Local development / Small teams**: Docker on a single machine
- **Production / Enterprise**: Kubernetes for scalability and orchestration

### Requirements

1. **Unified interface**: Same code for starting reviews, regardless of backend
2. **Backend-specific features**: Support Docker networks, Kubernetes node selectors, etc.
3. **Shared logic**: Common code for Redis tracking, status publishing, log parsing
4. **Easy to extend**: Adding new backends (e.g., Podman, ECS) should be straightforward

## Decision

Use an **abstract base class** (`ContainerBackend`) with concrete implementations for each platform.

### Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                    ContainerPlugin                          │
│  - Selects backend based on config                          │
│  - Manages lifecycle (startup/shutdown)                     │
│  - Runs reconciliation loop                                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ uses
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  ContainerBackend (ABC)                     │
├─────────────────────────────────────────────────────────────┤
│ Concrete methods (shared logic):                            │
│  - register_execution()                                     │
│  - unregister_execution()                                   │
│  - get_active_executions()                                  │
│  - publish_status()                                         │
│  - publish_status_idempotent()                              │
│  - acquire_reconcile_lock()                                 │
├─────────────────────────────────────────────────────────────┤
│ Abstract methods (platform-specific):                       │
│  - start_container()                                        │
│  - stop_container()                                         │
│  - start_watching()                                         │
│  - stop_watching()                                          │
│  - reconcile()                                              │
└─────────────────────────────────────────────────────────────┘
              ▲                               ▲
              │                               │
              │ implements                    │ implements
              │                               │
┌─────────────────────────┐     ┌─────────────────────────┐
│     DockerBackend       │     │   KubernetesBackend     │
├─────────────────────────┤     ├─────────────────────────┤
│ - aiodocker client      │     │ - kr8s API client       │
│ - Docker event stream   │     │ - K8s watch API         │
│ - Container lifecycle   │     │ - Job lifecycle         │
└─────────────────────────┘     └─────────────────────────┘
```

### Abstract Base Class

```python
class ContainerBackend(ABC):
    """Abstract base for container backends (Docker, K8s)."""

    def __init__(self, broker: RedisBroker, redis: Redis):
        self._broker = broker
        self._redis = redis

    # Shared implementations
    async def register_execution(self, execution_id: str) -> None: ...
    async def publish_status_idempotent(self, ...) -> bool: ...

    # Platform-specific (must implement)
    @abstractmethod
    async def start_container(self, execution_id: str, job: ReviewJobMessage) -> str: ...

    @abstractmethod
    async def start_watching(self) -> None: ...

    @abstractmethod
    async def reconcile(self) -> None: ...
```

### Backend Selection

```python
class ContainerPlugin(BasePlugin):
    async def startup(self) -> None:
        if self.config.backend == "docker":
            self._backend = DockerBackend(self.config.docker, broker, redis)
        else:
            self._backend = KubernetesBackend(self.config.kubernetes, broker, redis)
```

### Shared Utilities

Platform-agnostic logic is extracted to `utils.py`:

```python
# Label keys (same for Docker and K8s)
LABEL_EXECUTION_ID = "reviewate.execution_id"

# Log parsing (same structured format)
def parse_structured_logs(log_text: str) -> tuple[dict | None, str | None]: ...

# Status determination (same logic)
def determine_execution_status(exit_code, result, error) -> tuple[str, str | None]: ...

# CLI args building (same code_reviewer interface)
def build_cli_args(job: ReviewJobMessage) -> list[str]: ...
```

### Configuration Structure

```python
class ContainerPluginConfig(BaseModel):
    enabled: bool = False
    backend: Literal["docker", "kubernetes"] = "docker"
    watcher: WatcherConfig = WatcherConfig()
    docker: DockerConfig | None = DockerConfig()
    kubernetes: KubernetesConfig | None = None
```

Each backend has its own config with platform-specific options:

**Docker**:

- `socket`: Path to Docker socket
- `network`: Docker network name
- `memory_limit`, `cpu_limit`: Resource constraints

**Kubernetes**:

- `namespace`: K8s namespace
- `service_account`: Pod service account
- `node_selector`, `tolerations`: Scheduling
- `run_as_user`, `run_as_group`: Security context

## Alternatives Considered

### 1. Single Implementation with Conditionals

**Approach**: One class with `if backend == "docker"` checks throughout.

**Why rejected**:

- Code becomes hard to maintain as backends diverge
- No clear separation of concerns
- Difficult to add new backends

### 2. Strategy Pattern with Composition

**Approach**: Inject strategy objects for each operation (starting, watching, reconciling).

**Why rejected**:

- Over-engineered for current needs (only 2 backends)
- More objects to manage
- Abstract base class is simpler and sufficient

### 3. Separate Plugins per Backend

**Approach**: `DockerPlugin` and `KubernetesPlugin` as independent plugins.

**Why rejected**:

- Duplicates shared logic (Redis tracking, status publishing)
- Configuration becomes fragmented
- Harder to switch backends

## Consequences

### Positive

- **Clean separation**: Platform-specific code isolated in each backend
- **Code reuse**: Shared logic in base class and utilities
- **Type safety**: Abstract methods enforced at class definition
- **Easy testing**: Mock the base class for consumer tests
- **Extensibility**: New backend = new class implementing abstract methods

### Negative

- **Inheritance coupling**: Changes to base class affect all backends
- **Method signature constraints**: Abstract methods must have compatible signatures

### Neutral

- **Two config sections**: Docker and Kubernetes configs coexist (only one used)
- **Backend consistency**: Both backends must support the same abstract interface

## Implementation Notes

### Adding a New Backend

1. Create `backend/api/plugins/container/newbackend.py`
2. Implement all abstract methods from `ContainerBackend`
3. Add config class to `config.py`
4. Add selection logic to `plugin.py`

### Backend-Specific Extensions

If a backend needs unique capabilities not in the abstract interface:

- Add methods directly to the concrete class
- Access via type narrowing: `if isinstance(backend, KubernetesBackend): ...`
