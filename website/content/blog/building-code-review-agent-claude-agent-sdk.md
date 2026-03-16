---
title: "Building a Code Review Agent with the Claude Agent SDK"
description: "How we built a multi-agent code review pipeline using the Claude Agent SDK — structured output, tool budgets, parallel agents, and the patterns that emerged."
date: "2026-03-16"
badge: "Engineering"
---

Reviewate's code review pipeline runs seven agents in sequence. Each agent is a Python class that wraps a single call to the [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview). Here's how we built it and the patterns that emerged.

## Why the Claude Agent SDK

Before the SDK, we were orchestrating Claude via raw API calls — managing tool schemas, parsing tool use blocks, looping on tool results, handling retries. It worked, but the code was brittle and most of it was plumbing.

The Claude Agent SDK gives you `query()` — an async generator that handles the agentic loop internally. You pass a prompt, configure tools, and iterate over messages. The SDK manages tool execution, conversation state, and structured output. We deleted hundreds of lines of orchestration code.

```python
from claude_agent_sdk import ClaudeAgentOptions, query

options = ClaudeAgentOptions(
    system_prompt="You are a code reviewer.",
    permission_mode="bypassPermissions",
    allowed_tools=["Read", "Grep", "Glob", "Bash"],
    max_turns=12,
    model="sonnet",
    cwd="/path/to/repo",
)

async for message in query(prompt="Review this PR", options=options):
    # Handle AssistantMessage, ResultMessage, etc.
    ...
```

The key insight: the SDK gives you Claude Code's tool implementations (Read, Grep, Glob, Bash) for free. These are the same tools Claude Code uses — battle-tested, permission-aware, and optimized for code exploration. We don't implement any tools ourselves.

## The BaseAgent Pattern

Every agent in the pipeline is a subclass of `BaseAgent`. The pattern is agent-as-configuration — subclasses set class-level attributes, and the base class handles everything else:

```python
class AnalyzeAgent(BaseAgent):
    prompt_file = "analyze.md"
    permission_mode = "bypassPermissions"
    allowed_tools = ["Skill", "Read", "Grep", "Glob", "Bash"]
    disallowed_tools = ["Agent", "Task"]
    max_turns = 12

class StyleAgent(BaseAgent):
    prompt_file = "style.md"
    allowed_tools: list[str] = []  # No tools — single-turn transform
    max_turns = 1
    output_schema = StyleResult
```

`BaseAgent.__init__` loads the markdown prompt, optionally renders it as a Jinja2 template, builds `ClaudeAgentOptions`, and `invoke()` runs `query()` and collects the result:

```python
result = await AnalyzeAgent(
    model="sonnet",
    platform="github",
    pr_description=pr_body,
    diff=diff_text,
    cwd=repo_dir,
).invoke("Review this PR")

# result.text — full text output
# result.structured_output — parsed JSON (if output_schema set)
# result.cost_usd, result.num_turns, result.usage — telemetry
```

This is the entire interface. No chains, no graphs, no state machines. Each agent is a function call that returns a result.

## Structured Output

Most agents in the pipeline need to return structured data — not free-form text. The SDK supports this via `output_format`:

```python
class FilterResult(BaseModel):
    keep_indices: list[int]

class FactCheckAgent(BaseAgent):
    output_schema = FilterResult
    # ...
```

`BaseAgent` converts the Pydantic model to a JSON schema and passes it as `output_format` to the SDK:

```python
if self.output_schema:
    kwargs["output_format"] = {
        "type": "json_schema",
        "schema": self.output_schema.model_json_schema(),
    }
```

The SDK enforces the schema on Claude's output. This is what makes the pipeline possible — each agent's output is a typed contract that the next stage can rely on. The fact-checker returns `FilterResult(keep_indices=[0, 2, 5])`, and the pipeline applies it mechanically. No parsing, no regex, no hoping the model follows instructions.

We use four output schemas across the pipeline:

| Schema | Used by | Shape |
|--------|---------|-------|
| `Review[Comment]` | Analyzer, Synthesizer | `{"comments": [{"path", "line", "body", ...}]}` |
| `FilterResult` | Dedup, Fact-Checker | `{"keep_indices": [0, 2, 5]}` |
| `StyleResult` | Style | `{"bodies": ["...", "...", "..."]}` |
| `IssueExplorerOutput` | Issue Explorer | `{"context": "...", "issue_refs": ["..."]}` |

## Tool Budgets via Hooks

Agents with code search tools (Analyzer, Fact-Checker) can spiral — searching endlessly, reading every file, never producing output. We needed a hard cap on tool calls without truncating the conversation.

The SDK supports [hooks](https://platform.claude.com/docs/en/agent-sdk/overview) — shell commands that execute on events like `PreToolUse`. We wrote a 50-line Python hook that counts tool calls and denies them when the budget is exceeded:

```python
# hooks/tool_budget.py (PreToolUse hook)
budget = int(os.environ.get("REVIEWATE_TOOL_BUDGET", "9999"))
counter_file = f"/tmp/reviewate_budget_{session_id}"

# ... count calls ...

if count > budget:
    json.dump({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"TOOL BUDGET EXHAUSTED ({count}/{budget}). "
                "Output your findings IMMEDIATELY."
            ),
        }
    }, sys.stdout)
```

`BaseAgent` writes a temporary `.claude/settings.json` in the agent's working directory to register the hook, sets `REVIEWATE_TOOL_BUDGET` in the environment, and cleans up after the agent completes.

The budget is derived from `max_turns`: we reserve 2 turns (one for the denied call, one for the final output). So `max_turns=12` means a budget of 10 tool calls. The Analyzer gets 10 calls to explore code. The Fact-Checker gets 23 (from `max_turns=25`).

The denial message is critical — it tells the model to stop exploring and output what it has. Without this, the model would try alternative tools or rephrase the same request.

## Running Agents in Parallel

The two analyzer agents run in parallel via `asyncio.gather`:

```python
raw_results = await asyncio.gather(
    AnalyzeAgent(name="Analyzer[0]", model=review_model, ...).invoke(prompt),
    AnalyzeAgent(name="Analyzer[1]", model=review_model, ...).invoke(prompt),
    return_exceptions=True,
)
```

`return_exceptions=True` is important — one analyzer crashing shouldn't kill the pipeline. We filter out exceptions and continue with whatever results we got:

```python
analyzer_results = []
for r in raw_results:
    if isinstance(r, BaseException):
        logger.warning("Analyzer failed: %s", r)
    else:
        analyzer_results.append(r)
```

This is one of the advantages of the SDK's `query()` being an async generator — it composes naturally with asyncio. No special parallelism primitives needed.

## Two-Tier Model System

Not every agent needs the same model. We split agents into two tiers:

| Tier | Agents | Model | Why |
|------|--------|-------|-----|
| **Review** | Analyzer (x2), Fact-Checker | Sonnet | Deep reasoning with code tools |
| **Utility** | Synthesizer, Dedup, Style, Issue Explorer | Haiku | Single-turn transforms, no tools |

The review tier agents are agentic — they make decisions about which files to read, what to search for, and whether evidence supports a finding. This requires strong reasoning.

The utility tier agents are pure transforms — they receive structured input and produce structured output in a single turn with no tool access. Haiku handles this well and is significantly cheaper.

Each agent receives its model as a constructor parameter. The pipeline runner (`RunContext`) holds `review_model` and `utility_model`, configured via environment variables.

## Jinja2 Prompt Templates

Agent prompts are markdown files in `prompts/`. Several agents need platform-specific instructions (GitHub vs GitLab have different comment schemas), so we use Jinja2 templating:

```python
class AnalyzeAgent(BaseAgent):
    prompt_file = "analyze.md"

    def __init__(self, *, platform="github", pr_description="", diff="", **kwargs):
        super().__init__(
            template_vars={
                "platform": platform,
                "pr_description": pr_description,
                "diff": diff,
            },
            **kwargs,
        )
```

`BaseAgent.load_system_prompt()` renders the template:

```python
def load_system_prompt(self):
    text = Path(self.prompt_file).read_text()
    if self.template_vars:
        from jinja2 import Template
        text = Template(text).render(**self.template_vars)
    return text
```

This lets us bake the PR diff and description directly into the system prompt — the agent doesn't waste tool calls reading information we already have. The diff and PR body are pre-fetched once and injected into every agent that needs them.

## Blocking Recursive Agents

One subtle issue: when an agent has access to the `Skill` tool (which loads CLAUDE.md and project context), it can also discover the `Agent` and `Task` tools. An analyzer agent could theoretically spawn sub-agents and re-run the entire review pipeline recursively.

The fix: `disallowed_tools`.

```python
class AnalyzeAgent(BaseAgent):
    allowed_tools = ["Skill", "Read", "Grep", "Glob", "Bash"]
    disallowed_tools = ["Agent", "Task"]
```

The SDK passes this as `--disallowedTools` to the underlying CLI, preventing the agent from using these tools even if it discovers them.

## What We Learned

**The SDK is the right abstraction level.** It handles the agentic loop, tool execution, and message parsing. We handle the pipeline — what agents to run, in what order, with what inputs. This separation is clean and hasn't needed to change as we've iterated on the pipeline.

**Structured output is non-negotiable for pipelines.** Every agent-to-agent boundary needs a typed contract. Free-form text works for single-agent systems but breaks down when agents need to compose. The SDK's `output_format` makes this reliable.

**Tool budgets matter more than max_turns.** `max_turns` limits conversation rounds, but an agent can make multiple tool calls per turn. The PreToolUse hook gives us precise control over exploration depth, and the denial message ensures graceful degradation.

**Parallel agents are trivially composable.** Because `query()` is async, running multiple agents in parallel is just `asyncio.gather()`. No special infrastructure needed.

**Thin wrappers beat frameworks.** `BaseAgent` is ~150 lines of code. It loads a prompt, builds options, runs `query()`, and collects results. There's no agent graph, no state machine, no chain abstraction. Each agent is a function call. The pipeline is a Python function with `await` calls. This is easy to debug, easy to test, and easy to change.

---

*Reviewate is open source under AGPL v3. [View the source on GitHub](https://github.com/numberly/reviewate) or [read the quickstart guide](/docs/getting-started/quickstart).*
