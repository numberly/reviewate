# ADR-006: Multi-Cluster Job Execution

**Status**: Proposed
**Date**: 2026-02-18

## Context

Reviewate currently executes code review Jobs on a **single cluster**. The `KubernetesBackend` connects to one API server (via in-cluster ServiceAccount or local kubeconfig), creates Jobs in one namespace, and watches events from that cluster only.

As adoption grows, single-cluster execution hits several walls:

1. **Regional latency**: Customers in different regions want reviews to run close to their infrastructure
2. **Capacity limits**: One cluster has finite node capacity; burst workloads can exhaust resources
3. **Blast radius**: A cluster failure takes down all job execution
4. **Compliance**: Some customers may require jobs to run in specific regions or cloud providers

### Current Architecture (Single Cluster)

```text
┌──────────────┐     ┌───────┐     ┌──────────────────────┐
│   Backend    │────▶│ Redis │◀────│   KubernetesBackend  │
│  (API +      │     │       │     │  - start_container()  │
│   webhooks)  │     │       │     │  - watch loop         │
└──────────────┘     └───────┘     │  - reconcile()        │
                                   │  → 1 cluster API      │
                                   │  → 1 namespace        │
                                   └──────────────────────┘
```

### Limitations

| Component | Limitation |
|---|---|
| `kr8s.asyncio.api()` | Auto-discovers **local** cluster only |
| `kr8s.asyncio.watch("jobs", namespace=...)` | Watches **one** namespace in **one** cluster |
| `Job.list(namespace=...)` in reconcile | Lists Jobs from **one** cluster |
| `reviewate:executions:active` Redis set | Global set with no cluster scoping |
| FastStream Redis channels (pub/sub) | Every consumer gets every message — no partitioned consumption |

## Decision

Adopt a **Federated Workers** model: deploy a backend instance per cluster, all sharing the same Redis and database. Each instance runs `KubernetesBackend` pointed at its local cluster's API server and consumes jobs from a shared work queue.

### Architecture

```text
                    ┌──────────────────────┐
                    │    Shared Redis      │
                    │  (managed, regional  │
                    │   or cross-region)   │
                    └──────┬───────────────┘
                           │
              ┌────────────┼────────────────┐
              │            │                │
              ▼            ▼                ▼
     ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
     │  Cluster A   │ │  Cluster B   │ │  Cluster C   │
     │  (eu-west)   │ │  (us-east)   │ │  (ap-south)  │
     │              │ │              │ │              │
     │  Backend     │ │  Backend     │ │  Backend     │
     │  instance    │ │  instance    │ │  instance    │
     │  + K8sBackend│ │  + K8sBackend│ │  + K8sBackend│
     │  (local API) │ │  (local API) │ │  (local API) │
     └──────────────┘ └──────────────┘ └──────────────┘
```

Each cluster instance:
- **Consumes** jobs from a shared Redis Stream (not pub/sub)
- **Creates** Jobs on the local K8s API
- **Watches** local Job events and publishes status back to Redis
- **Reconciles** only its own cluster's Jobs

One designated instance (or a separate lightweight deployment) handles:
- Webhook ingress (GitHub/GitLab)
- API serving (dashboard, manual triggers)
- Database migrations

### Key Changes

#### 1. Cluster Identity

Add a `cluster_id` to `KubernetesConfig`:

```python
class KubernetesConfig(BaseModel):
    cluster_id: str = "default"          # NEW — unique per deployment
    namespace: str = "reviewate-jobs"
    # ... existing fields
```

#### 2. Scoped Redis Tracking

Partition the active execution set by cluster so reconciliation is scoped:

```python
# Before (global)
ACTIVE_EXECUTIONS_KEY = "reviewate:executions:active"

# After (per-cluster)
def active_executions_key(cluster_id: str) -> str:
    return f"reviewate:executions:active:{cluster_id}"
```

Store the `cluster_id` alongside the execution so the status handler knows origin:

```python
# Status message gains cluster_id
message = {
    "execution_id": execution_id,
    "cluster_id": self._cluster_id,   # NEW
    "status": status,
    ...
}
```

#### 3. Redis Streams for Job Distribution

Replace FastStream pub/sub on `reviewate.review.jobs` with a **Redis Stream + Consumer Group**. This gives exactly-once delivery across multiple consumers:

```python
# Publishing (unchanged call site, FastStream handles it)
await broker.publish(job_message, stream="reviewate.review.jobs")

# Consuming (each cluster instance joins the same consumer group)
@router.subscriber(
    stream=StreamSub(
        "reviewate.review.jobs",
        group="review-workers",
        consumer=config.kubernetes.cluster_id,  # unique consumer name
    )
)
async def handle_review_job(message: ReviewJobMessage): ...
```

With consumer groups, Redis delivers each job to **exactly one** consumer in the group. No duplicate processing, no missed jobs.

#### 4. Execution Model Update

Add `cluster_id` to the `Execution` database model:

```python
class Execution(Base):
    # ... existing fields
    cluster_id: str | None = None   # NEW — which cluster ran this
```

#### 5. Reconciliation Scoping

Each instance only reconciles its own Jobs:

```python
async def reconcile(self) -> None:
    # Only get this cluster's active executions
    active = await self.get_active_executions()  # uses per-cluster key

    # List Jobs — already scoped to local cluster (kr8s talks to local API)
    job_map = {}
    async for job_obj in Job.list(namespace=self._config.namespace, ...):
        ...

    # Orphan detection only for this cluster's executions
    orphaned = active - set(job_map.keys())
```

### Webhook & API Routing

For the initial implementation, **all instances can serve the API** behind a load balancer. Webhook handlers publish to the shared Redis Stream — any worker picks it up. No routing intelligence needed at this stage.

Future refinement: add optional affinity hints (e.g., prefer a cluster in the same region as the repository's Git provider) by publishing to cluster-specific streams.

### Migration Path

1. **Phase 1 — Scoped Redis keys + cluster_id**: Add `cluster_id` config, scope the active execution set, add `cluster_id` to Execution model and status messages. Single-cluster deployments use `cluster_id: "default"` and behave identically.

2. **Phase 2 — Redis Streams**: Migrate `reviewate.review.jobs` from pub/sub channel to Redis Stream with consumer group. This also improves reliability for single-cluster (messages persist, can be replayed on failure).

3. **Phase 3 — Multi-cluster deployment**: Deploy a second backend instance in another cluster, joining the same consumer group. Validate job distribution, status reporting, and reconciliation.

## Alternatives Considered

### 1. Central Dispatcher + Remote Agents

**Approach**: Keep a single backend that dispatches jobs to remote clusters via multi-context kubeconfigs. Deploy lightweight watcher agents in each cluster that report status back.

```text
Central Backend ──kubeconfig──▶ Cluster A
                ──kubeconfig──▶ Cluster B
Each cluster: watcher agent ──▶ Redis
```

**Why not preferred**:
- Requires managing kubeconfig credentials for remote clusters (security risk, rotation burden)
- Central dispatcher is a single point of failure for job creation
- Watcher agent is a new component to build and operate
- Cross-cluster API calls add latency and failure modes

### 2. Kubernetes Federation (KubeFed / Admiralty / Liqo)

**Approach**: Use a K8s federation layer that transparently schedules Jobs across clusters.

**Why not preferred**:
- Significant infrastructure complexity (another control plane to operate)
- KubeFed is deprecated; alternatives (Liqo, Admiralty) are less mature
- Opaque scheduling decisions — harder to debug and reason about
- Overkill for our workload (short-lived, stateless Jobs)

### 3. Cloud-Native Job Services (GCP Cloud Run Jobs / AWS Batch)

**Approach**: Replace K8s Jobs with a managed serverless job service.

**Why not preferred**:
- Vendor lock-in (contradicts our multi-platform strategy)
- Would require a third `ContainerBackend` implementation
- Less control over networking isolation and security context
- Could be added later as another backend (ADR-004 supports this)

## Consequences

### Positive

- **Horizontal scaling**: Add capacity by adding clusters, not scaling individual nodes
- **Regional execution**: Jobs run close to where they're needed
- **Fault isolation**: One cluster going down doesn't stop all reviews
- **Incremental adoption**: Phase 1-2 improve single-cluster reliability with no multi-cluster required
- **Backward compatible**: `cluster_id: "default"` preserves current single-cluster behavior exactly

### Negative

- **Operational complexity**: More instances to deploy, monitor, and upgrade
- **Redis becomes critical path**: Shared Redis must be highly available (use managed Redis with replication)
- **Schema migration**: `cluster_id` column on `Execution` table
- **Eventual consistency**: A job's status update travels through Redis before reaching the database — already true today, but more visible across clusters

### Neutral

- **No changes to `ContainerBackend` interface**: The abstract class stays the same; changes are in config, Redis key naming, and FastStream transport
- **Docker backend unaffected**: Multi-cluster only applies to Kubernetes deployments
- **Code reviewer container unchanged**: It doesn't know or care which cluster it runs in
