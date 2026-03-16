# ADR-001: Implicit Feedback Learning via LLM Semantic Canonicalization

**Status**: Proposed
**Date**: 2025-12-18

## Context

Reviewate generates code review comments for pull requests. Users can provide feedback on these reviews through:

- Emoji reactions (thumbs down on unhelpful comments)
- Reply comments ("we don't use pydantic, we use attrs")
- Resolved/dismissed reviews

Currently, this feedback is lost. We want to **learn from feedback** to improve future reviews without requiring users to manually configure every preference.

### Requirements

1. **Two-layer guideline system**:
   - **Explicit**: User-defined rules in dashboard (e.g., "always suggest type hints")
   - **Implicit**: Auto-learned rules from feedback patterns

2. **Open source friendly**: Must work without heavy dependencies or infrastructure

3. **Cost effective**: Should add minimal overhead to review costs

4. **Accurate matching**: Same feedback about the same topic should reinforce one rule, not create duplicates

## Decision

Use **LLM-based semantic canonicalization** to extract and match learned preferences.

### How It Works

```md
User Feedback → LLM Canonicalization → Semantic Key → Match/Create Rule → Update Confidence
```

1. **Canonicalization**: LLM extracts structured rule from natural language feedback
2. **Semantic Key**: Normalized identifier for matching (e.g., `validation:prefer:attrs:avoid:pydantic`)
3. **Confidence Tracking**: Rules gain confidence with reinforcement, decay over time

### Core Schema

```python
class RuleCanonicalization(BaseModel):
    """Structured representation of a coding preference."""
    rule: str                    # Human-readable: "Use attrs instead of pydantic"
    semantic_key: str            # Normalized: "validation:prefer:attrs:avoid:pydantic"
    category: Literal[
        "library_preference",    # Use X library over Y
        "pattern_preference",    # Use X pattern over Y
        "style_preference",      # Formatting, naming conventions
        "practice_preference"    # Best practices, approaches
    ]
    action: Literal["prefer", "avoid", "require", "forbid"]
    target: str | None           # What to use/do
    avoid: str | None            # What not to use/do
    domain: str                  # Area: "validation", "testing", "logging", etc.
```

### Database Model

```python
class ImplicitGuideline(Base):
    __tablename__ = "implicit_guidelines"

    id: Mapped[UUID]
    organization_id: Mapped[UUID]
    repository_id: Mapped[UUID | None]  # None = org-wide

    # Rule content
    rule: Mapped[str]
    semantic_key: Mapped[str]
    category: Mapped[str]
    domain: Mapped[str]
    action: Mapped[str]
    target: Mapped[str | None]
    avoid: Mapped[str | None]

    # Confidence tracking
    confidence: Mapped[float]           # 0.0 - 1.0
    signal_count: Mapped[int]           # Times reinforced
    contradiction_count: Mapped[int]    # Times contradicted

    # Timestamps
    created_at: Mapped[datetime]
    last_reinforced: Mapped[datetime]
```

### Confidence Algorithm

```python
def update_confidence(guideline: ImplicitGuideline, is_reinforcement: bool) -> float:
    """Update confidence with diminishing returns."""
    if is_reinforcement:
        guideline.signal_count += 1
        # Diminishing returns: 1st signal = +0.3, 5th = +0.1, 10th = +0.05
        increment = 0.3 / (1 + 0.5 * guideline.signal_count)
        guideline.confidence = min(1.0, guideline.confidence + increment)
    else:
        guideline.contradiction_count += 1
        guideline.confidence = max(0.0, guideline.confidence - 0.2)

    guideline.last_reinforced = datetime.utcnow()
    return guideline.confidence
```

### Prompt Injection

Learned rules are injected into review agent prompts:

```python
def build_review_prompt(diff: str, guidelines: list[ImplicitGuideline]) -> str:
    high_confidence = [g for g in guidelines if g.confidence >= 0.6]

    rules_section = "\n".join([
        f"- {g.rule} (confidence: {g.confidence:.0%})"
        for g in sorted(high_confidence, key=lambda x: -x.confidence)
    ])

    return f"""
## Learned Team Preferences
{rules_section}

Apply these preferences when relevant to the code being reviewed.
"""
```

## Alternatives Considered

### 1. RAG with Embeddings

**Approach**: Store feedback as embeddings, retrieve similar past feedback via vector similarity.

**Why rejected**:

- Requires vector database (pgvector, Pinecone, Qdrant)
- Requires embedding model (OpenAI, Cohere, or local 500MB+ model)
- Similarity ≠ equivalence (similar text might mean different things)
- Would need LLM verification anyway to confirm match

### 2. PAMU (Preference-Aware Memory Update)

**Approach**: Research paper approach using Sliding Window + EMA for preference tracking with specialized models.

**Why rejected**:

- Requires RoBERTa, SKEP, OpenNRE models
- Too heavy for open source deployment
- Designed for conversational agents, not code review

### 3. Explicit Configuration Only

**Approach**: Only use dashboard-configured rules, no implicit learning.

**Why rejected**:

- Misses opportunity to learn from organic feedback
- Requires users to manually configure everything
- Doesn't capture team conventions that emerge organically

## Consequences

### Positive

- **No extra infrastructure**: Uses existing LLM, no vector DB needed
- **Accurate matching**: LLM understands intent, not just text similarity
- **Open source friendly**: Works with any LLM provider
- **Cost effective**: ~$0.01/month at 250 MRs (see cost analysis)
- **Deterministic matching**: Same semantic key = same rule

### Negative

- **LLM dependency**: Requires LLM call per feedback event
- **Potential hallucination**: LLM might extract incorrect rules (mitigated by confidence tracking)
- **No fuzzy matching**: Might miss related but differently-phrased feedback

### Neutral

- **Requires prompt engineering**: Quality depends on canonicalization prompt
- **Cold start**: New orgs have no learned preferences initially

## Cost Analysis

### Assumptions

- 250 MRs/month, 25% feedback rate = ~62 feedback events
- ~800 input tokens, ~250 output tokens per event

### Monthly Cost by Model

| Model | Cost/Month |
|-------|-----------|
| Gemini 2.0 Flash | $0.01 |
| GPT-4o-mini | $0.02 |
| Claude 3.5 Haiku | $0.10 |

### Scaling

| Scale | MRs/Month | Feedback Events | Cost (Gemini) |
|-------|-----------|-----------------|---------------|
| Small | 250 | 62 | $0.01 |
| Medium | 1,000 | 250 | $0.04 |
| Large | 5,000 | 1,250 | $0.20 |
| Enterprise | 25,000 | 6,250 | $1.00 |

## Comparison: Embeddings vs LLM Canonicalization

| Factor | Embeddings | LLM Canonicalization |
|--------|------------|---------------------|
| Infrastructure | Vector DB required | None |
| Dependencies | Embedding model | Existing LLM |
| Accuracy | Similarity-based | Intent-based |
| Matching | Fuzzy threshold | Deterministic |
| Open source | Heavy | Lightweight |
| Cost | Similar | ~$0.01/month |

## Implementation Notes

### Phase 1: Core Learning

1. Add `implicit_guidelines` table
2. Implement canonicalization prompt
3. Add feedback webhook handlers
4. Basic matching by semantic key

### Phase 2: Integration

1. Inject learned rules into review prompts
2. Add confidence decay job (weekly)
3. Dashboard UI to view/manage implicit rules

### Phase 3: Advanced

1. Repository vs org-level rules
2. Rule inheritance (org → repo)
3. Conflict detection between explicit and implicit rules

## References

- PAMU Paper: Preference-Aware Memory Update for Conversational Recommender Systems
- Industry patterns: .cursorrules, .coderabbit.yaml, CLAUDE.md
