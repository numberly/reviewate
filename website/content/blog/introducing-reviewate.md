---
title: "Introducing Reviewate: AI Code Reviews That Find Real Bugs"
description: "Meet the open-source, multi-agent code review system that catches bugs, security issues, and logic errors in your pull requests."
date: "2025-07-15"
badge: "Launch"
---

## Why Another Code Review Tool?

Most AI code review tools are glorified linters. They flag style issues, suggest variable renames, and generate noise that developers learn to ignore. We built Reviewate to be different.

Reviewate uses a **multi-agent pipeline** where each stage has a specific job. The result: fewer, higher-quality findings that point to actual bugs in your code.

## The Pipeline

Every pull request goes through a multi-agent pipeline powered by the [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview):

1. **Review** — 2 analyzer agents with code search tools independently explore the codebase in parallel, finding bugs, security issues, and logic errors
2. **Fact-Check** — A separate agent verifies each finding against the actual codebase using code search tools
3. **Style** — Rewrites findings into concise, scannable comments

The fact-checker is the key differentiator. It has access to the full repository and can verify whether a finding is real or a hallucination. This is what takes precision from ~30% (typical for AI review tools) to **57%**.

## Benchmarks

We tested Reviewate on the [Augment Code benchmark](https://github.com/ai-code-review-evaluations) — 50 PRs with confirmed bugs across [Sentry](https://github.com/adamsaimi/sentry-20260213-0023), [Grafana](https://github.com/adamsaimi/grafana-20260213-0023), Greptile, [Cal.com](https://github.com/adamsaimi/cal_dot_com-20260213-0023), and [Discourse](https://github.com/adamsaimi/discourse-20260213-0023). Results with **Gemini 3 Flash**:

- **65.7% of real bugs caught** (recall)
- **57.3% of findings are actionable** (precision)
- **< 3 minutes** per review

## Self-Hosted & Open Source

Reviewate is AGPL-3.0 licensed and designed to run on your infrastructure. Your code never leaves your network. Deploy with Docker or Kubernetes, bring your own LLM API keys, and configure everything to match your team's workflow.

## Get Started

1. Clone the repository from [GitHub](https://github.com/numberly/reviewate)
2. Configure your LLM provider and repository settings
3. Set up the webhook for GitHub or GitLab
4. Start getting AI code reviews on every PR

Check out the [quickstart guide](/docs/getting-started/quickstart) to start getting AI code reviews on your PRs today.
