# ADR-003: Redis-Based Execution Tracking with Idempotent Status Updates

**Status**: Accepted
**Date**: 2025-01-29

## Context

Container watchers (see ADR-002) can process the same container exit from multiple sources:

- Event handler receives "die" or "Complete" event
- Reconciliation loop finds exited container
- Multiple watcher instances running simultaneously

Without deduplication, the same execution could be marked complete multiple times, leading to:

- Duplicate database updates
- Duplicate webhook deliveries
- Race conditions in downstream consumers

### Requirements

1. **At-most-once processing**: Each container exit should be processed exactly once
2. **No database dependency**: Watchers shouldn't need database access for deduplication
3. **Fast lookups**: Checking if execution is active should be O(1)
4. **Distributed**: Work across multiple watcher instances

## Decision

Use **Redis** for execution tracking with **atomic idempotent status publishing**.

### Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                         Redis                               │
├─────────────────────────────────────────────────────────────┤
│  reviewate:executions:active  (SET)                         │
│  ├── execution-id-1                                         │
│  ├── execution-id-2                                         │
│  └── execution-id-3                                         │
├─────────────────────────────────────────────────────────────┤
│  reviewate:reconcile:lock  (STRING with TTL)                │
│  └── "1" (held by one instance)                             │
├─────────────────────────────────────────────────────────────┤
│  reviewate.execution.status  (PUB/SUB channel)              │
│  └── { execution_id, status, result, ... }                  │
└─────────────────────────────────────────────────────────────┘
```

### Execution Lifecycle

```text
Container Start                    Container Exit
      │                                  │
      ▼                                  ▼
┌─────────────┐                ┌─────────────────────┐
│ SADD active │                │ SREM active         │
│ set         │                │ (atomic check)      │
└─────────────┘                └─────────────────────┘
                                         │
                               ┌─────────┴─────────┐
                               │                   │
                         removed=1           removed=0
                               │                   │
                               ▼                   ▼
                        ┌───────────┐       ┌───────────┐
                        │ Publish   │       │ Skip      │
                        │ status    │       │ (already  │
                        │           │       │ processed)│
                        └───────────┘       └───────────┘
```

### Key Operations

**Register Execution** (on container start):

```python
await redis.sadd(ACTIVE_EXECUTIONS_KEY, execution_id)
```

**Idempotent Status Publish** (on container exit):

```python
async def publish_status_idempotent(self, execution_id: str, status: str, ...):
    if status in ("completed", "failed"):
        # Atomic check-and-remove
        removed = await self._redis.srem(ACTIVE_EXECUTIONS_KEY, execution_id)
        if not removed:
            return False  # Already processed by another handler

    await self.publish_status(execution_id, status, ...)
    return True
```

**Get Active Executions** (for reconciliation):

```python
members = await redis.smembers(ACTIVE_EXECUTIONS_KEY)
```

### Distributed Locking for Reconciliation

Only one instance should run reconciliation at a time:

```python
async def acquire_reconcile_lock(self) -> bool:
    acquired = await self._redis.set(
        RECONCILE_LOCK_KEY,
        "1",
        nx=True,   # Only set if not exists
        ex=60,     # TTL prevents deadlock
    )
    return bool(acquired)
```

### Why Redis SREM is Atomic

Redis SREM returns the number of elements removed. When multiple handlers call `SREM` for the same execution_id concurrently:

- First caller: `SREM` returns 1, proceeds to publish
- Second caller: `SREM` returns 0, skips (already removed)

This is atomic because Redis is single-threaded for command execution.

## Alternatives Considered

### 1. Database-Based Tracking

**Approach**: Store active executions in PostgreSQL, use `SELECT FOR UPDATE` for locking.

**Why rejected**:

- Adds database dependency to watchers
- Higher latency for lock acquisition
- More complex transaction handling
- Potential for deadlocks

### 2. In-Memory Tracking

**Approach**: Track active executions in process memory.

**Why rejected**:

- Lost on process restart
- Doesn't work with multiple instances
- No persistence

### 3. Kubernetes Annotations/Labels

**Approach**: Store "processed" flag in Kubernetes Job annotations.

**Why rejected**:

- Only works for Kubernetes backend
- Requires additional API calls
- Race conditions between read and update

### 4. Message Deduplication in Consumer

**Approach**: Let consumer handle duplicates via database constraints.

**Why rejected**:

- Duplicates still flow through the system
- Consumer complexity increases
- Doesn't prevent duplicate side effects (webhooks, notifications)

## Consequences

### Positive

- **Exactly-once processing**: SREM atomicity guarantees single processing
- **Fast**: Redis operations are sub-millisecond
- **Distributed**: Works across multiple watcher instances
- **Simple**: No complex locking logic, Redis handles atomicity
- **Decoupled**: Watchers don't need database access

### Negative

- **Redis dependency**: Requires Redis to be available
- **Memory usage**: Active set grows with concurrent executions (minimal, just UUIDs)
- **TTL management**: No automatic cleanup of stale entries (handled by reconciliation)

### Neutral

- **Consistency window**: Brief window where execution is in Redis but container hasn't started
- **Recovery**: On Redis data loss, reconciliation repopulates from container runtime
