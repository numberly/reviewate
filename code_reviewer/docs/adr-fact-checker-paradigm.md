# ADR: Fact Checker Paradigm

## Status

Proposed

## Context

The fact checker verifies AI-generated code review claims against actual codebases. It receives reviews claiming bugs exist, uses tools (grep, read_file, read_lines) to search the code, and decides KEEP (real bug) or DISCARD (false positive).

### Current performance

- **Overall accuracy**: 66% on 261 reviews (40 test cases across sentry, discourse, keycloak, grafana)
- **cal_dot_com**: 59% on 61 reviews (10 test cases) — worst project
- **Pipeline impact**: Precision 30% → 33% (negligible), Recall 75% → 57% (significant loss)
- **FPR**: 50-67% depending on project — keeps too many false positives
- **Token usage**: ~10.5M tokens for 40 cases

### Root cause analysis

Every failure follows the same pattern:

1. Model reads review claim ("there's a bug at X")
2. Model searches code, finds X exists
3. Model says "X exists → bug confirmed" → KEEP

The model never asks: **"is this behavior actually wrong?"** It confirms the claim's narrative and stops. It never searches for contradicting evidence (tests, safeguards, comments, alternative code paths).

Prompt engineering iterations (3-test framework, minimal prompt, middle-ground) all hit the same wall: the model confirmation-biases its search.

### Baseline numbers

Without fact checker: Precision = 30%, Recall = 75%
Target: Precision ≥ 50%, Recall ≥ 60%

---

## Options

### Option A: Current Approach — Single-Pass Classification

**How it works:**

- One LLM call per batch of reviews
- Model gets: diff + reviews + tools
- Model searches code, decides KEEP/DISCARD per review
- Single conversation, all reviews at once

**Strengths:**

- Simple, fast, cheap (1 LLM call per batch)
- Low latency (single round)

**Weaknesses:**

- Confirmation bias: finds matching pattern → assumes bug
- Never searches for contradicting evidence
- Batch processing divides attention across reviews
- Prompt engineering hasn't solved the core issue after 5+ iterations

**Current results:** 66% accuracy, FPR 50-67%

---

### Option B: Evidence-First Workflow (2 phases)

**How it works:**
Phase 1 — **Gather** (per review, can be cheap model):

- "For this review, find: the claimed code, tests covering this path, callers, safeguards. Report everything you find. Do NOT make a KEEP/DISCARD decision."
- Output: structured evidence report

Phase 2 — **Judge** (reasoning model):

- Receives: review claim + complete evidence report
- "Given this evidence, is the bug reproducible? KEEP or DISCARD."
- No tool access — decides purely from provided evidence

**Strengths:**

- Forces thorough evidence gathering before judgment
- Prevents early hypothesis lock-in
- Phase 1 can use a cheap model (just searching, not reasoning)
- Phase 2 has full context to reason about

**Weaknesses:**

- 2x LLM calls per review (more tokens, more latency)
- Phase 1 might still miss important evidence
- Evidence report quality depends on search prompts

**Implementation:**

- Phase 1: Explorer agent with structured output (claimed_code, tests, callers, safeguards)
- Phase 2: Judge agent receives evidence report, makes decision

---

### Option C: Adversarial Verification (2 agents)

**How it works:**
Agent 1 — **Advocate** (tries to PROVE the bug):

- "Search the codebase for evidence that this bug is real. Build the strongest case you can."
- Output: evidence supporting the claim

Agent 2 — **Skeptic** (tries to DISPROVE the bug):

- "Search the codebase for evidence that this is NOT a bug. Find tests that pass, safeguards, comments explaining it's intentional, alternative code paths."
- Output: evidence against the claim

Judge — **Decision** (weighs both sides):

- Receives both evidence sets
- KEEP only if Advocate's case is stronger AND Skeptic couldn't disprove

**Strengths:**

- Directly solves the "never searches for contradicting evidence" problem
- Skeptic is explicitly tasked with finding disconfirming evidence
- Adversarial structure prevents confirmation bias by design
- Judge sees both sides before deciding

**Weaknesses:**

- 3x LLM calls per review (expensive)
- Higher latency
- Advocate and Skeptic might search the same code redundantly
- Complexity in aggregating results

**Implementation:**

- Advocate: Explorer agent with "prove this bug" prompt
- Skeptic: Explorer agent with "disprove this bug" prompt
- Judge: Classification agent with both evidence sets, no tools

---

### Option D: Reproduction-Based Verification

**How it works:**
Single agent, reframed question:

- "Trace the execution path described in this review. Start from the entry point, follow the code step by step, and determine: does the failure described actually occur?"
- Model must explicitly trace: caller → function → arguments → return → failure point
- If it can trace a concrete path to failure → KEEP
- If it cannot reproduce the failure (hits a safeguard, wrong types, tests prove otherwise) → DISCARD

**Strengths:**

- Reframes from classification ("KEEP?") to reproduction ("can you demo the bug?")
- Forces step-by-step reasoning, not pattern matching
- Natural way to discover safeguards (they appear in the trace)
- Closest to how a human developer would verify

**Weaknesses:**

- Still single-pass (could still confirmation-bias)
- Some bugs don't have clear "trace" (design issues, missing validation)
- Requires model to do multi-step code tracing (expensive reasoning)
- May need high reasoning effort to trace properly

**Implementation:**

- Same architecture as current, different prompt framing
- Prompt asks for explicit execution trace before decision
- Could combine with chain-of-thought / structured output

---

### Option E: Structured Checklist Search

**How it works:**
Single agent, but with mandatory search steps before deciding:

1. **Read the claimed code** — read_file or read_lines at the exact location
2. **Search for tests** — grep for test files covering this function/module
3. **Search for callers** — grep for who calls this function
4. **Search for safeguards** — grep for error handling, validation, guards near the code
5. **Report findings** — list what each step found
6. **Decide** — based on all evidence

The agent MUST complete all 5 search steps before making a decision. The prompt enforces this with structured output.

**Strengths:**

- Simple to implement (prompt change + structured output)
- Forces the model to search for contradicting evidence (tests, safeguards)
- Low overhead (still 1 LLM call, just more structured tool usage)
- Checklist prevents skipping important searches

**Weaknesses:**

- Rigid checklist might not fit all review types
- Could waste tool calls on irrelevant searches
- Still single-pass reasoning (bias possible after gathering)
- Model might "go through the motions" without deep analysis

**Implementation:**

- Modify prompt to require checklist completion
- Use structured output: `{evidence: {code, tests, callers, safeguards}, decision, reason}`
- Code enforcement: reject if evidence sections are empty

---

### Option F: Per-Review Deep Verification (no batching)

**How it works:**
Instead of batching N reviews per LLM call, verify each review individually:

- 1 review per LLM call
- Full tool budget dedicated to this single claim
- Model can do 10-20 tool calls focused on ONE review
- No attention splitting across reviews

Combined with any of the above prompting strategies (evidence-first, reproduction, checklist).

**Strengths:**

- Full attention on each review (no batch dilution)
- More tool calls per review = deeper search
- Each verification is independent (easy to parallelize)
- Simpler prompting (no "for each review" instructions)

**Weaknesses:**

- N × LLM calls instead of ceil(N/batch_size) (more expensive)
- No shared context between reviews (can't spot duplicates)
- Higher total latency if not parallelized
- Token overhead from repeating diff/context per call

**Implementation:**

- Set BATCH_SIZE = 1
- Or create a separate `verify_single_review()` method
- Parallelize all reviews with semaphore for rate limiting

---

## Decision Matrix

| Criteria | A (Current) | B (Evidence-First) | C (Adversarial) | D (Reproduction) | E (Checklist) | F (Per-Review) |
|----------|:-----------:|:------------------:|:---------------:|:-----------------:|:-------------:|:--------------:|
| Solves confirmation bias | No | Yes | Yes | Partial | Partial | No* |
| Forces contradicting evidence search | No | Yes | Yes (Skeptic) | Partial | Yes | No* |
| Implementation complexity | Low | Medium | High | Low | Low | Low |
| LLM calls per review | 1/batch | 2 | 3 | 1/batch | 1/batch | 1 |
| Token cost | Low | Medium | High | Medium | Medium | Medium |
| Latency | Low | Medium | High | Medium | Low | Low** |
| Can combine with others | — | +D,E,F | +F | +B,E,F | +B,D,F | +B,C,D,E |

*F doesn't solve bias on its own but amplifies whatever strategy it's combined with
**Low per-review if parallelized

## Recommended Test Plan

Test each option on the same subset: `cal_dot_com-feat-convert-insightsbookings` (5 reviews, hardest case).
Then expand winner to full 50-case benchmark.

Combinations worth testing:

1. E alone (cheapest improvement)
2. B alone (strongest paradigm shift)
3. D + F (reproduction with full attention per review)
4. B + F (evidence-first with per-review focus)
5. C + F (adversarial with per-review focus, most expensive)
