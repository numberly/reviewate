---
title: "How We Reduced False Positives in AI Code Review by 50%"
description: "False positives kill AI code review adoption. Here's the technical approach we used to cut noise in half — and why fact-checking against the actual codebase is the key."
date: "2025-09-10"
badge: "Engineering"
---

The number one complaint about AI code review tools is false positives. When most of your automated findings are wrong, developers learn to click "dismiss" without reading. You've spent engineering effort to make your review process *worse*.

We spent months reducing Reviewate's false positive rate. Here's what worked, what didn't, and the architecture that finally got us to a useful signal-to-noise ratio.

## Why LLMs Hallucinate in Code Review

When an LLM reviews a code diff, it sees a narrow window of the codebase. It doesn't know:

- What functions exist elsewhere in the project
- What types or interfaces are defined
- Whether a pattern is intentional or accidental
- What the test coverage looks like

So it guesses. And LLMs are very good at generating plausible-sounding but incorrect analysis. A typical hallucinated finding looks like:

> "The variable `config` could be null here. Add a null check before accessing `config.timeout`."

This sounds reasonable. But if you check the actual code, `config` is initialized three lines above and can never be null. The LLM didn't have that context.

## Approach 1: Better Prompts (Marginal Improvement)

Our first attempt was prompt engineering. We added instructions like "only flag issues you're confident about" and "don't report style issues." This helped marginally — maybe a 10% reduction in false positives — but fundamentally couldn't fix the problem. The model doesn't know what it doesn't know.

## Approach 2: Bigger Context Window (Didn't Scale)

Next we tried stuffing more code into the context window. Include the full file, related files, type definitions. This helped with some hallucinations but created new problems:

- Token costs exploded
- The model started hallucinating about the *surrounding* code instead
- Review times went from seconds to minutes
- It still couldn't access code outside the included files

## Approach 3: Fact-Checking with Tools (The Breakthrough)

The approach that actually worked was separating **generation** from **verification**.

An issue explorer fetches linked issues from the PR description for context. Then two analyzer agents (each with code search tools like Read, Grep, Glob, and Bash) independently explore the codebase and generate candidate findings in parallel. A synthesizer merges and deduplicates across reviewers. Finally, a dedicated fact-checker agent receives each finding and verifies it against the actual codebase using code search and file reads.

The fact-checker's job is to *disprove* each finding. It asks:

- Does the referenced function/variable actually exist?
- Is the claimed behavior actually possible given the surrounding code?
- Is there already a guard or check that handles this case?

If it can't find evidence that the finding is wrong, the finding survives. If it finds counter-evidence, the finding is discarded.

### The Results

| Metric | Before fact-checking | After fact-checking |
|--------|---------------------|-------------------|
| Precision (actionable findings) | ~30% | **57.3%** |
| Recall (bugs caught) | ~72% | **65.7%** |
| Total findings per PR | ~15 | **~5** |

*Measured with Gemini 3 Flash on the [Augment Code benchmark](https://github.com/ai-code-review-evaluations) — 50 PRs across [Sentry](https://github.com/adamsaimi/sentry-20260213-0023), [Grafana](https://github.com/adamsaimi/grafana-20260213-0023), Greptile, [Cal.com](https://github.com/adamsaimi/cal_dot_com-20260213-0023), and [Discourse](https://github.com/adamsaimi/discourse-20260213-0023).*

The trade-off is clear: we lose some true positives (recall drops from 72% to 65.7%) but nearly double precision. In practice, the recall loss is worth the 27-point precision gain because developers actually read the remaining findings.

## Key Technical Decisions

### Sequential, Not Parallel Tool Use

We initially let the fact-checker call multiple tools in parallel. This was faster but less accurate — the model would commit to a conclusion before seeing all the evidence. Switching to sequential tool calls (one at a time, each informed by previous results) improved accuracy significantly.

### Trust the First Result

A counter-intuitive finding: telling the model to "trust the first code search result" improved accuracy. Without this instruction, the model would search repeatedly, find ambiguous results, and talk itself into keeping false positives. The first search result is usually the most relevant.

### Can't Prove It = Discard It

The most impactful rule: if the fact-checker can't find concrete code evidence that a finding is valid, it discards the finding. This biases toward precision over recall, which matches what developers actually want.

## The Model Matters More Than the Prompt

After extensive prompt optimization, we found that the single biggest lever is the **model itself**. On the same test cases:

- Weaker models scored 3/7 on our verification benchmark
- Stronger reasoning models scored 6/7

No amount of prompt engineering can compensate for reasoning depth. If your budget allows it, use the best available model for the fact-checking stage.

## Practical Takeaways

If you're building or evaluating AI code review:

1. **Separate generation from verification** — don't try to do both in one pass
2. **Give the verifier access to the full codebase** — context windows aren't enough
3. **Bias toward precision** — fewer, correct findings beat many, noisy findings
4. **Measure on real bugs** — synthetic benchmarks don't predict real-world performance
5. **Budget for the best model on verification** — this is where reasoning depth pays off

---

*Reviewate is open source and free to self-host. [Try it on your codebase](/docs/getting-started/quickstart) or [read the source](https://github.com/numberly/reviewate).*
