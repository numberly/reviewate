# ADR-002: Event-Driven Container Watching with Periodic Reconciliation

**Status**: Accepted
**Date**: 2025-01-29

## Context

Reviewate executes code reviews in isolated containers (Docker or Kubernetes). We need to monitor container lifecycle events (started, completed, failed) and publish status updates to downstream consumers via Redis.

### Requirements

1. **Real-time status updates**: Users should see review status changes quickly
2. **Reliability**: No container exit should go unnoticed, even during watcher restarts
3. **Scalability**: Support multiple backend instances watching containers
4. **Low overhead**: Avoid polling the container runtime constantly

### Challenges

- Container events can be missed if the watcher restarts
- Docker/Kubernetes event streams can disconnect
- Multiple instances watching the same containers can cause duplicate processing

## Decision

Use an **event-driven watching pattern** with **periodic reconciliation** as a safety net.

### Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                     Container Runtime                       │
│                   (Docker / Kubernetes)                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ Event Stream
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Event Watcher                          │
│  - Subscribes to container/job events                       │
│  - Filters by reviewate labels                              │
│  - Bounded concurrency (semaphore)                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ Publish Status
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                         Redis                               │
│  - Status channel (reviewate.execution.status)              │
│  - Active executions set                                    │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┴─────────────────────┐
        │                                           │
        ▼                                           ▼
┌───────────────────┐                   ┌───────────────────┐
│  Reconcile Loop   │                   │  Status Consumer  │
│  (every 60s)      │                   │  (updates DB)     │
└───────────────────┘                   └───────────────────┘
```

### Event-Driven Watching

Each backend subscribes to native events:

**Docker**:

```python
subscriber = docker.events.subscribe(
    filters={
        "type": ["container"],
        "label": [LABEL_EXECUTION_ID],
    }
)
```

**Kubernetes**:

```python
async for event_type, job_obj in kr8s.asyncio.watch(
    "jobs",
    namespace=namespace,
    label_selector=LABEL_EXECUTION_ID,
):
```

### Bounded Concurrency

Event handlers use a semaphore to prevent overwhelming the system:

```python
MAX_CONCURRENT_HANDLERS = 100
self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_HANDLERS)

async def _handle_event_with_limit(self, event):
    async with self._semaphore:
        await self._handle_event(event)
```

### Periodic Reconciliation

A background loop runs every N seconds (configurable, default 60s) to catch missed events:

```python
async def reconcile(self):
    # 1. List all containers/jobs with reviewate labels
    # 2. Check for exited/completed ones that weren't processed
    # 3. Handle orphaned executions (in Redis but container gone)
```

### Graceful Shutdown

On shutdown, pending event handlers are awaited with a timeout:

```python
if self._pending_tasks:
    await asyncio.wait_for(
        asyncio.gather(*self._pending_tasks, return_exceptions=True),
        timeout=30.0,
    )
```

## Alternatives Considered

### 1. Polling Only

**Approach**: Periodically list all containers and check their status.

**Why rejected**:

- High latency (status updates delayed by poll interval)
- Unnecessary load on container runtime API
- Scales poorly with container count

### 2. Events Only (No Reconciliation)

**Approach**: Trust events completely, no periodic checks.

**Why rejected**:

- Events can be missed during watcher restart
- Event stream can disconnect silently
- No recovery for edge cases

### 3. Database Polling

**Approach**: Poll database for pending executions, then check container status.

**Why rejected**:

- Requires database queries on every poll
- Couples watching to database schema
- Higher latency than event-driven

## Consequences

### Positive

- **Low latency**: Status updates published within milliseconds of events
- **Reliable**: Reconciliation catches any missed events
- **Efficient**: No constant polling, events are pushed
- **Bounded resource usage**: Semaphore prevents runaway concurrency

### Negative

- **Complexity**: Two code paths (events + reconcile) for the same logic
- **Potential duplicates**: Same exit can be processed by event and reconcile (mitigated by idempotency, see ADR-003)

### Neutral

- **Reconcile interval tuning**: Too short = unnecessary work, too long = delayed recovery
- **Event stream reconnection**: Both Docker and Kubernetes require reconnection logic on disconnect
