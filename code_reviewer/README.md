# Reviewate - AI-Powered Code Review

**Reviewate** is a multi-agent code review system for GitHub and GitLab pull requests. Powered by the Claude Agent SDK, it explores your codebase, verifies every finding against actual code, and posts only fact-checked feedback.

## Requirements

- **LLM auth**: Anthropic API key, Claude subscription (via CLI login), or `CLAUDE_CODE_OAUTH_TOKEN`
- **Platform**: `gh`/`glab` CLI logged in, or `GITHUB_TOKEN`/`GITLAB_TOKEN` env var

## Quick Start

### Install

```bash
pip install reviewate   # or: uv tool install reviewate
```

### Run a review

```bash
# From a PR/MR URL (platform, repo, PR auto-detected):
reviewate https://github.com/facebook/react/pull/28000

# Or with owner/repo + PR number:
reviewate facebook/react -p 28000

# First run: prompts for model choice, saves to ~/.reviewate/config.toml
```

No token needed if the `gh` or `glab` CLI is logged in.

### From source (for development)

```bash
git clone https://github.com/numberly/reviewate.git
cd reviewate/code_reviewer
uv sync

uv run python main.py facebook/react -p 28000
```

## Authentication

| Method | Best for | Setup |
|--------|----------|-------|
| **CLI Auth** | Local development | Log in with `gh auth login` or `glab auth login` |
| **API Token** | CI pipelines, Docker, self-hosted | Set `GITHUB_TOKEN` or `GITLAB_TOKEN` |

## CLI Options

```bash
# From PR/MR URL (auto-detects platform, repo, PR number):
reviewate https://github.com/org/repo/pull/48
reviewate https://gitlab.com/group/repo/-/merge_requests/1
reviewate https://gitlab.example.com/group/sub/project/-/merge_requests/352

# Classic format:
reviewate owner/repo -p 123                    # review (default)
reviewate summary owner/repo -p 123            # summary only
reviewate full owner/repo -p 123               # review + summary
reviewate review owner/repo -p 123 --dry-run   # explicit review

# Configuration
reviewate config                               # re-run setup wizard

# Additional flags
reviewate owner/repo -p 123 \
  --platform gitlab \                           # GitLab (default: github)
  --dry-run \                                   # Don't post comments
  --debug \                                     # Enable debug logging
  --json \                                      # Output results as JSON
```

## Architecture

### Multi-Agent Pipeline

Powered by the [Claude Agent SDK](https://docs.anthropic.com/en/docs/agents-and-tools/claude-agent-sdk). Agents use Claude Code's built-in tools (Read, Grep, Glob, Bash) for codebase exploration.

```text
PR Diff
  │
  ▼
Issue Explorer + 2 Analyze Agents (parallel, with Read/Grep/Glob/Bash)
                │
                ▼
           Synthesizer ──▶ Deduplicate ──▶ Fact Checker ──▶ Style
                                                              │
                                                              ▼
                                                   Guardrail (secret scan)
                                                              │
                                                              ▼
                                                        Post Comments
```

1. **IssueExplorerAgent** — Finds and summarizes linked issues
2. **AnalyzeAgent** (x2, parallel) — Reviews code with Read/Grep/Glob/Bash tools
3. **SynthesizerAgent** — Combines findings from both reviewers
4. **DedupAgent** — Removes duplicates with existing human comments
5. **FactCheckAgent** — Verifies every claim against actual code
6. **StyleAgent** — Final formatting (makes reviews concise)
7. **Guardrail** — Scans findings for leaked secrets (gitleaks-based) before posting

### Two-Tier Model Configuration

Agents are grouped into tiers so you can use a strong model for critical analysis and a fast/cheap model for supporting tasks:

| Tier | Agents | Purpose |
|------|--------|---------|
| **Review** | AnalyzeAgent (x2), FactCheckAgent | Critical analysis |
| **Utility** | SynthesizerAgent, DedupAgent, StyleAgent, IssueExplorerAgent, SummarizerAgent, SummaryParserAgent | Supporting tasks |

### Code Structure

```text
code_reviewer/
├── main.py              # CLI entry point & main() loop
├── cli.py               # Argument parsing & URL resolution
├── runner.py            # Config validation & workflow execution
├── config.py            # Simple env var based configuration
├── config_file.py       # ~/.reviewate/config.toml handling
├── output.py            # Progress tracking & result output
├── schemas.py           # Data models (ReviewComment, Review, FilterResult, etc.)
├── guardrail.py         # Gitleaks-based secret scanning before posting
├── adaptors/
│   ├── factory.py       # Platform handler factory
│   └── repository/      # GitHub/GitLab handlers (gh api / glab api)
├── agents/
│   ├── base.py          # BaseAgent (wraps claude_agent_sdk.query())
│   ├── analyzer.py      # AnalyzeAgent (Read/Grep/Glob/Bash, sonnet)
│   ├── synthesizer.py   # SynthesizerAgent (no tools, haiku, 1 turn)
│   ├── deduplicator.py  # DedupAgent (no tools, haiku, 1 turn)
│   ├── fact_checker.py  # FactCheckAgent (Read/Grep/Glob, sonnet)
│   ├── styler.py        # StyleAgent (no tools, haiku, 1 turn)
│   ├── post_fixer.py    # PostingFixAgent (Bash, fixes line numbers)
│   ├── issue_explorer.py
│   ├── summary.py       # SummarizerAgent (no tools, haiku, structured output)
│   └── summary_parser.py # SummaryParserAgent (no tools, haiku, structured output)
├── workflows/
│   ├── context.py       # RunContext shared state
│   ├── review/
│   │   ├── runner.py    # Review pipeline orchestration
│   │   └── utils.py     # Pipeline helpers (parse, filter, style, post)
│   └── summary/
│       └── runner.py    # Summary pipeline orchestration
├── prompts/             # Jinja2 prompt templates (.md)
└── hooks/               # Tool budget hooks
```

## Environment Variables

All env vars are **optional** if you have a config file (`~/.reviewate/config.toml`). Env vars override config file values when set.

**Authentication (depends on auth mode chosen during `reviewate config`):**

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key (mode 1: API key, mode 3: custom endpoint) |
| `CLAUDE_CODE_OAUTH_TOKEN` | OAuth token for headless/container use (mode 2: subscription). Locally, CLI session is used — no env var needed |

**Model configuration:**

| Variable | Description |
|----------|-------------|
| `REVIEWATE_REVIEW_MODEL` | Review tier model (default: `sonnet`) |
| `REVIEWATE_UTILITY_MODEL` | Utility tier model (default: `haiku`) |
| `REVIEWATE_BASE_URL` | Custom base URL (e.g., LiteLLM proxy) |

**Platform tokens:**

| Variable | Description |
|----------|-------------|
| `GITHUB_TOKEN` | GitHub token (optional with `gh` CLI) |
| `GITLAB_TOKEN` | GitLab token (optional with `glab` CLI) |

**Self-hosted platforms:**

| Variable | Default | Description |
|----------|---------|-------------|
| `GITLAB_HOST` | `https://gitlab.com` | GitLab self-hosted instance URL |

**Override priority:** env vars > config file > defaults

## Development

```bash
# From monorepo root
make code-review-test  # Run tests
make qa                # Run linters and type checks
```

## License

AGPL-3.0 — see LICENSE file for details.
