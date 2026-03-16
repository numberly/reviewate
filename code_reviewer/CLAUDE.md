# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# From monorepo root
make code-review-test  # Run all tests
make qa                # Run pre-commit checks (ruff lint/format)

# Run a review (installed via uvx/pip)
reviewate owner/repo -p 123                    # review (default)
reviewate summary owner/repo -p 123            # summary only
reviewate full owner/repo -p 123               # review + summary

# Run a review (from source)
uv run python main.py owner/repo -p 123
```

## Architecture

### Claude Agent SDK

Reviewate uses the **Claude Agent SDK** (`claude-agent-sdk`) with Python-driven pipelines. Each step is a standalone `BaseAgent` subclass:

**Review pipeline** (`workflows/review/runner.py`):
```
  Step 1a: IssueExplorerAgent                  → linked issue context
  Step 1b: asyncio.gather(AnalyzeAgent × 2)    → raw findings (with issue context)
  Step 2:  SynthesizerAgent                    → merged & deduplicated
  Step 3:  DedupAgent (if discussions exist)   → filtered vs human comments
  Step 4:  FactCheckAgent                      → verified findings
  Step 5:  StyleAgent (output_schema=StyleResult) → styled bodies
```

**Summary pipeline** (`workflows/summary/runner.py`):
```
  Step 1: IssueExplorerAgent                   → linked issue context
  Step 2: SummarizerAgent                      → SummaryOutput (structured)
  Step 3: SummaryParserAgent                   → ParsedSummaryOutput (refined)
  Step 4: format_summary() (Jinja2 template)   → markdown string
  Step 5: handler.post_regular_comment()       → post to platform
```

### Agent Classes

Each agent is in its own file under `agents/`:
- `BaseAgent` (`agents/base.py`) — Wraps `claude_agent_sdk.query()`, loads markdown prompts, builds `ClaudeAgentOptions`
- `AnalyzeAgent` (`agents/analyzer.py`) — Code reviewer with Read/Grep/Glob/Bash tools
- `SynthesizerAgent` (`agents/synthesizer.py`) — Merges & deduplicates findings from parallel reviewers (no tools, 1 turn)
- `DedupAgent` (`agents/deduplicator.py`) — Filters findings already covered by existing PR comments (no tools, 1 turn)
- `FactCheckAgent` (`agents/fact_checker.py`) — Verifies findings against actual code with Read/Grep/Glob
- `StyleAgent` (`agents/styler.py`) — Formats findings into structured JSON with output_schema (no tools, 1 turn)
- `PostingFixAgent` (`agents/post_fixer.py`) — Fixes line numbers when posting fails (Bash only)
- `SummarizerAgent` (`agents/summary.py`) — Generates PR/MR summary bullet points (no tools, 1 turn, structured output)
- `SummaryParserAgent` (`agents/summary_parser.py`) — Refines/condenses summary (no tools, 1 turn, structured output)

### Posting

Review findings are posted programmatically by the handler (not by agents):
- Inline comments attached to specific diff lines; fallback to regular comments
- Retry loop (max 1) with `PostingFixAgent` to fix line numbers on failure

### Prompts

All agent prompts are markdown files in `prompts/`:
- `analyze.md` — Analyzer agent
- `synthesize.md` — Synthesizer agent (merge & dedup across reviewers)
- `dedup.md` — Deduplication agent (Jinja2 template with discussions)
- `fact-check.md` — Fact checker agent
- `style.md` — Style formatter agent (Jinja2 template with platform-specific JSON output)
- `summarizer.md` — Summarizer agent prompt
- `summary-parser.md` — Summary parser/refiner agent prompt
- `summary-template.md` — Jinja2 template for final summary markdown

### Configuration

Simple env var based configuration:

- `ANTHROPIC_API_KEY` — API key for Claude
- `CLAUDE_CODE_OAUTH_TOKEN` — OAuth token (for Claude Max)
- `REVIEWATE_BASE_URL` — Custom base URL (for LiteLLM proxy)
- `REVIEWATE_REVIEW_MODEL` — Review tier model override
- `REVIEWATE_UTILITY_MODEL` — Utility tier model override
- `GITHUB_TOKEN` — GitHub token (also used by `gh` CLI)
- `GITLAB_TOKEN` — GitLab token (for `glab` CLI)
- `GITLAB_HOST` — GitLab self-hosted API URL

### Platform Interaction

Uses `gh` and `glab` CLI tools via subprocess calls:

- `gh pr view`, `gh pr diff`, `gh pr comment`, `gh api` for GitHub
- `glab mr view`, `glab mr diff`, `glab mr note`, `glab api` for GitLab

### Code Exploration

Claude Code's built-in tools handle everything:

- `Read` — Read files
- `Grep` — Search code with ripgrep
- `Glob` — Find files by pattern
- `Bash` — Run commands

## Guidelines

- Tests use `pytest-asyncio` with `asyncio_mode = "auto"`
- Mock external SDK calls with `@patch("code_reviewer.agents.base.query")`
- All imports should be at the top level (no relative imports)
- Always use pydantic for types
