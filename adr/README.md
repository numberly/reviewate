# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for Reviewate.

## What is an ADR?

An ADR is a document that captures an important architectural decision made along with its context and consequences.

## Format

Each ADR follows this structure:

- **Title**: Short descriptive name
- **Status**: Proposed | Accepted | Deprecated | Superseded
- **Context**: What is the issue we're facing?
- **Decision**: What is the change we're proposing?
- **Alternatives Considered**: What other options did we evaluate?
- **Consequences**: What are the trade-offs?

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [001](./001-implicit-feedback-learning.md) | Implicit Feedback Learning via LLM Semantic Canonicalization | Proposed |
| [002](./002-event-driven-container-watching.md) | Event-Driven Container Watching with Periodic Reconciliation | Accepted |
| [003](./003-redis-execution-tracking-idempotency.md) | Redis-Based Execution Tracking with Idempotent Status Updates | Accepted |
| [004](./004-pluggable-container-backend.md) | Pluggable Container Backend Architecture | Accepted |
| [005](./005-skills-system.md) | Skills System for Enhanced Code Review | Proposed |
