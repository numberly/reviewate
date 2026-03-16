---
title: "Multi-Agent Architecture for Code Review: Why One LLM Call Isn't Enough"
description: "Single-pass AI code review hits a ceiling. Here's how a multi-agent pipeline with specialized stages produces dramatically better results."
date: "2025-11-01"
badge: "Architecture"
---

The simplest way to build an AI code reviewer is to send the diff to an LLM and ask it to find bugs. Most tools do exactly this. And it works — to a point.

The problem is that a single LLM call is trying to do too many things at once: understand the changes, identify what's risky, find bugs, avoid false positives, and write clear comments. Each of these tasks has different requirements, and optimizing for one often hurts another.

Reviewate uses a multi-agent pipeline powered by the [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview) where each stage has a single job. Here's why this architecture produces better results.

## The Single-Pass Ceiling

In our testing, a single LLM call for code review typically achieved:

- **~40% recall** — catches about 4 out of 10 real bugs
- **~25% precision** — only 1 in 4 findings is actionable
- **~15 findings per PR** — most of which are noise

These numbers were consistent across models and prompts we tested. You can improve them incrementally with better prompting, but the fundamental limitation is that one pass through the diff isn't enough context to distinguish real issues from hallucinations.

## The Pipeline

Reviewate's pipeline has two core stages, surrounded by supporting agents:

### 1. Review

**Job:** Find candidate issues.

Two analyzer agents explore the codebase in parallel — each with access to code search tools (Read, Grep, Glob, Bash). They clone the repository, read the diff, search related code, and generate candidate findings: potential bugs, security issues, logic errors, and edge cases.

At this stage, we optimize for **recall** — catch as many real issues as possible, even at the cost of some false positives. It's easier to filter out false positives later than to recover missed bugs.

A synthesizer agent then merges findings from both analyzers, removing duplicates and resolving contradictions.

### 2. Fact-Check

**Job:** Verify each finding against the actual codebase.

This is the critical stage. The fact-checker receives each finding and has access to code search tools — it can grep the repository and read related code.

For each finding, it asks: "Can I find evidence in the actual code that this issue is real?" If it can't, the finding is discarded.

This is where precision jumps from ~30% to ~57%. The fact-checker eliminates hallucinations, misunderstandings about the codebase, and findings about code that's already handled correctly.

### Supporting Stages

Around these two core stages, additional agents handle context and polish:

- **Issue Explorer** — Fetches linked issues from the PR description for context
- **Deduplication** — Filters findings that duplicate existing human comments on the PR
- **Style** — Rewrites surviving findings into concise, scannable markdown

## Why Separate Agents?

The key architectural decision is using separate agents instead of a single agent with multiple passes. There are three reasons:

### 1. Different Optimization Targets

The review stage optimizes for recall (catch everything). The fact-check stage optimizes for precision (eliminate false positives). These are opposing objectives — trying to do both in one pass forces a compromise that produces mediocre results on both.

### 2. Different Tool Access

Both the review agents and the fact-checker have access to code search tools (grep, file reads), but they use them differently. The reviewers explore broadly to find candidate issues. The fact-checker focuses narrowly on verifying specific claims. This separation means the fact-checker starts with fresh context and isn't biased by the reviewers' reasoning.

### 3. Different Model Requirements

Not every stage needs the same model. Issue exploration, synthesis, and styling can use smaller, faster models. The analyzers and fact-checker benefit from stronger reasoning models. This two-tier approach lets you optimize cost vs. quality per stage.

## The Cost of Complexity

A multi-agent pipeline is more complex than a single LLM call. There are more moving parts, more configuration options, and more things that can go wrong.

The trade-off is worth it when:

- **Precision matters** — if your team will ignore noisy findings, a single-pass tool is effectively useless
- **You review many PRs** — the pipeline cost is fixed engineering effort; per-PR costs are comparable to single-pass tools
- **You need verification** — for security-critical code, hallucinated findings can be worse than no findings

## Practical Numbers

On the [Augment Code benchmark](https://github.com/ai-code-review-evaluations) — 50 PRs with confirmed bugs across [Sentry](https://github.com/adamsaimi/sentry-20260213-0023), [Grafana](https://github.com/adamsaimi/grafana-20260213-0023), Greptile, [Cal.com](https://github.com/adamsaimi/cal_dot_com-20260213-0023), and [Discourse](https://github.com/adamsaimi/discourse-20260213-0023) (all results with **Gemini 3 Flash**). The single-pass baseline numbers reflect our own testing:

| Architecture | Recall | Precision | Findings/PR | Time |
|-------------|--------|-----------|-------------|------|
| Single-pass (our testing) | ~40% | ~25% | ~15 | ~1 min |
| Multi-agent (Reviewate) | **65.7%** | **57.3%** | **~5** | **< 3 min** |

The multi-agent pipeline catches more bugs, with fewer false positives, in a reasonable time. The only downside is the additional minutes of latency — which doesn't matter for asynchronous PR reviews.

## Building Your Own

If you want to experiment with multi-agent code review, Reviewate is fully open source. The pipeline is configurable:

- Swap models per stage
- Adjust review prompts for your conventions

The architecture is intentionally modular — each stage is an independent agent that can be tested, tuned, and replaced independently.

---

*Explore the architecture yourself. [View the source on GitHub](https://github.com/numberly/reviewate) or [read the quickstart guide](/docs/getting-started/quickstart).*
