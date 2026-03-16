"""Base agent wrapping the Claude Agent SDK.

All agents subclass BaseAgent which handles:
- Loading markdown prompts from code_reviewer/prompts/
- Building ClaudeAgentOptions
- Running query() and collecting the result
"""

from __future__ import annotations

import json as _json_mod
import logging
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TaskStartedMessage,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    query,
)
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Tool names that are SDK plumbing, not worth logging at INFO
_INTERNAL_TOOLS = {"ToolSearch"}

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
HOOK_SCRIPT = Path(__file__).parent.parent / "hooks" / "tool_budget.py"

T = TypeVar("T", bound=BaseModel)


class AgentResult:
    """Result from an agent invocation."""

    def __init__(
        self,
        text: str,
        cost_usd: float | None = None,
        duration_ms: int = 0,
        session_id: str = "",
        num_turns: int = 0,
        structured_output: Any | None = None,
        usage: dict[str, Any] | None = None,
    ) -> None:
        self.text = text
        self.cost_usd = cost_usd
        self.duration_ms = duration_ms
        self.session_id = session_id
        self.num_turns = num_turns
        self.structured_output = structured_output
        self.usage = usage or {}


class BaseAgent:
    """Base class for all Agent SDK agents.

    Subclasses set class-level attributes to configure behavior:
        prompt_file: markdown file in prompts/ to use as system prompt
        permission_mode: tool permission handling
        allowed_tools: tools the agent can use
        max_turns: max conversation turns (None = unlimited)
        model: model to use (None = default)
        agents: subagent definitions for Agent tool dispatch
    """

    prompt_file: str = ""
    permission_mode: str = "plan"
    allowed_tools: list[str] = []
    disallowed_tools: list[str] = []
    max_turns: int | None = None
    model: str | None = None
    agents: dict[str, AgentDefinition] | None = None
    output_schema: type[BaseModel] | None = None
    setting_sources: list[str] | None = None

    def __init__(
        self,
        *,
        name: str | None = None,
        cwd: str | Path | None = None,
        system_prompt_prefix: str = "",
        system_prompt_extra: str = "",
        debug: bool = False,
        env: dict[str, str] | None = None,
        template_vars: dict[str, Any] | None = None,
    ) -> None:
        self.name = name or self.__class__.__name__
        self.cwd = str(cwd) if cwd else None
        self.system_prompt_prefix = system_prompt_prefix
        self.system_prompt_extra = system_prompt_extra
        self.debug = debug
        self.env = env or {}
        self.template_vars = template_vars

    def load_system_prompt(self) -> str:
        """Load the markdown prompt file from prompts/.

        If template_vars is set, renders the prompt as a Jinja2 template.
        """
        if not self.prompt_file:
            return ""
        path = PROMPTS_DIR / self.prompt_file
        logger.debug("Loading prompt from %s", path)
        text = path.read_text()
        # Strip YAML front matter (--- ... ---) if present
        if text.startswith("---"):
            end = text.find("---", 3)
            if end != -1:
                text = text[end + 3 :].lstrip("\n")
        if self.template_vars:
            from jinja2 import Template

            text = Template(text).render(**self.template_vars)
        logger.debug("Prompt loaded (%d chars)", len(text))
        return text

    def _build_options(self) -> ClaudeAgentOptions:
        """Build ClaudeAgentOptions from agent configuration."""
        system_prompt = self.load_system_prompt()
        # Prefix goes before agent prompt for cache control
        if self.system_prompt_prefix:
            system_prompt = self.system_prompt_prefix + "\n\n" + system_prompt
        if self.system_prompt_extra:
            system_prompt += "\n\n" + self.system_prompt_extra

        # Use the agent's own prompt directly — no Claude Code preset.
        # Tools (Read, Grep, Glob, Bash) are defined by the SDK via the API
        # tool schema, not the system prompt.  Dropping the preset saves
        # ~10-12K tokens per call of irrelevant instructions.
        # Prepend minimal instructions so the model respects CLAUDE.md files
        # injected by setting_sources and uses tools effectively.
        preamble = (
            "You have access to tools for exploring code (Read, Grep, Glob, Bash). "
            "Use them to complete your task. "
            "If a CLAUDE.md file is loaded into context, follow its instructions."
        )
        system_prompt_value: str | None = (
            f"{preamble}\n\n{system_prompt}" if system_prompt else preamble
        )

        kwargs: dict[str, Any] = {
            "system_prompt": system_prompt_value,
            "permission_mode": self.permission_mode,
            "max_turns": self.max_turns,
            "cwd": self.cwd,
            "stderr": lambda line: logger.warning("%s: stderr: %s", self.name, line.rstrip()),
        }

        if self.model:
            kwargs["model"] = self.model
        if self.allowed_tools:
            kwargs["allowed_tools"] = list(self.allowed_tools)
        if self.disallowed_tools:
            kwargs["disallowed_tools"] = list(self.disallowed_tools)
        env = dict(self.env) if self.env else {}
        if self.max_turns and self.max_turns > 1 and self.allowed_tools:
            # Reserve 2 turns: 1 for the denied call + 1 for output
            env["REVIEWATE_TOOL_BUDGET"] = str(self.max_turns - 2)
        if env:
            kwargs["env"] = env
        if self.setting_sources:
            kwargs["setting_sources"] = list(self.setting_sources)
        if self.agents:
            kwargs["agents"] = self.agents
        if self.output_schema:
            kwargs["output_format"] = {
                "type": "json_schema",
                "schema": self.output_schema.model_json_schema(),
            }

        return ClaudeAgentOptions(**kwargs)

    def _setup_tool_budget_hook(self) -> None:
        """Write .claude/settings.json in cwd with the tool budget hook."""
        if not self.cwd or not self.max_turns or self.max_turns <= 1 or not self.allowed_tools:
            return
        if not HOOK_SCRIPT.exists():
            return

        settings_dir = Path(self.cwd) / ".claude"
        settings_file = settings_dir / "settings.json"

        # Preserve existing settings
        existing: dict = {}
        if settings_file.exists():
            try:
                existing = _json_mod.loads(settings_file.read_text())
            except (ValueError, OSError):
                pass
        self._original_settings: str | None = (
            settings_file.read_text() if settings_file.exists() else None
        )

        hooks = existing.get("hooks", {})
        pre_tool_use = hooks.get("PreToolUse", [])

        # Avoid adding duplicate hook entries
        hook_cmd = f"python3 {HOOK_SCRIPT}"
        if not any(hook_cmd in str(entry.get("hooks", [])) for entry in pre_tool_use):
            pre_tool_use.append(
                {
                    "matcher": "Read|Grep|Glob|Bash",
                    "hooks": [{"type": "command", "command": hook_cmd, "timeout": 5}],
                }
            )

        hooks["PreToolUse"] = pre_tool_use
        existing["hooks"] = hooks

        settings_dir.mkdir(parents=True, exist_ok=True)
        settings_file.write_text(_json_mod.dumps(existing, indent=2))

    def _cleanup_tool_budget_hook(self) -> None:
        """Restore original .claude/settings.json after agent completes."""
        if not self.cwd or not hasattr(self, "_original_settings"):
            return
        settings_file = Path(self.cwd) / ".claude" / "settings.json"
        original = self._original_settings
        try:
            if original is None:
                # We created it — remove it
                settings_file.unlink(missing_ok=True)
            else:
                settings_file.write_text(original)
        except OSError:
            pass

    async def invoke(
        self,
        user_prompt: str,
        *,
        on_tool_call: Callable[[str, str, dict], None] | None = None,
        on_task_started: Callable[[str, str], None] | None = None,
    ) -> AgentResult:
        """Run the agent with the given prompt and return the result.

        Args:
            user_prompt: The prompt to send to the agent.
            on_tool_call: Optional callback invoked for each ToolUseBlock with
                (tool_name, summary, input_dict).
            on_task_started: Optional callback invoked when a subagent task starts
                with (task_type, description).
        """
        agent_name = self.name
        logger.info("%s: starting (model=%s, cwd=%s)", agent_name, self.model, self.cwd)
        logger.debug("%s: prompt=%s", agent_name, user_prompt[:200])

        self._setup_tool_budget_hook()

        options = self._build_options()
        result_text = ""
        last_text_block = ""
        structured_output = None
        result_msg: ResultMessage | None = None

        try:
            async for message in query(prompt=user_prompt, options=options):
                if isinstance(message, TaskStartedMessage):
                    logger.info(
                        "%s: task started — %s (type=%s)",
                        agent_name,
                        message.description,
                        message.task_type,
                    )
                    if on_task_started is not None and message.task_type:
                        on_task_started(message.task_type, message.description)
                elif isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            if _is_fatal_error(block.text):
                                raise RuntimeError(block.text.strip())
                            last_text_block = block.text
                            text_preview = block.text if self.debug else block.text[:200]
                            logger.debug("%s: %s", agent_name, text_preview)
                        elif isinstance(block, ThinkingBlock) and self.debug:
                            logger.debug("%s: thinking: %s", agent_name, block.thinking)
                        elif isinstance(block, ToolUseBlock):
                            if block.name == "StructuredOutput":
                                raw = block.input
                                val = raw.get("output", raw) if isinstance(raw, dict) else raw
                                if isinstance(val, str):
                                    try:
                                        import json as _json

                                        val = _json.loads(val)
                                    except (ValueError, TypeError):
                                        pass
                                structured_output = val
                            summary = _tool_summary(block, self.cwd)
                            if block.name in _INTERNAL_TOOLS:
                                logger.debug(
                                    "%s: tool %s — %s",
                                    agent_name,
                                    block.name,
                                    summary,
                                )
                            else:
                                logger.info(
                                    "%s: tool %s — %s",
                                    agent_name,
                                    block.name,
                                    summary,
                                )
                            if on_tool_call is not None:
                                on_tool_call(block.name, summary, block.input)
                elif isinstance(message, ResultMessage):
                    result_msg = message
                    result_text = message.result or ""
                    if (
                        structured_output is None
                        and getattr(message, "structured_output", None) is not None
                    ):
                        structured_output = message.structured_output
        except RuntimeError as e:
            # The SDK uses anyio task groups internally. When invoke() runs
            # inside asyncio.gather (parallel analyzers), the async generator
            # cleanup can happen in a different task context, causing:
            #   "Attempted to exit cancel scope in a different task than
            #    it was entered in"
            # If we already captured useful output, swallow the error and
            # return what we have rather than losing the entire result.
            if "cancel scope" in str(e) and (last_text_block or structured_output):
                logger.warning("%s: SDK cleanup error (result preserved): %s", agent_name, e)
            else:
                raise
        finally:
            self._cleanup_tool_budget_hook()

        # The SDK's ResultMessage.result can be truncated. If parsing
        # fails downstream, the last TextBlock from AssistantMessage
        # usually has the complete output.
        if last_text_block and len(last_text_block) > len(result_text):
            result_text = last_text_block

        cost = result_msg.total_cost_usd if result_msg else None
        duration = result_msg.duration_ms if result_msg else 0
        num_turns = result_msg.num_turns if result_msg else 0
        usage = result_msg.usage if result_msg else None
        logger.info(
            "%s: done (%d turns, %.1fs, cost %s, %d chars, %s)",
            agent_name,
            num_turns,
            duration / 1000,
            f"${cost:.4f}" if cost else "n/a",
            len(result_text),
            _format_usage(usage),
        )

        return AgentResult(
            text=result_text,
            cost_usd=cost,
            duration_ms=duration,
            session_id=result_msg.session_id if result_msg else "",
            num_turns=num_turns,
            structured_output=structured_output,
            usage=usage,
        )

    async def invoke_structured(self, user_prompt: str, response_model: type[T]) -> T:
        """Run the agent and parse the result as a Pydantic model."""
        result = await self.invoke(user_prompt)
        text = _extract_json(result.text)
        return response_model.model_validate_json(text)


def _format_usage(usage: dict[str, Any] | None) -> str:
    """Format usage dict into a compact readable string."""
    if not usage:
        return "no usage"
    in_t = usage.get("input_tokens", 0)
    out_t = usage.get("output_tokens", 0)
    cache_r = usage.get("cache_read_input_tokens", 0)
    cache_w = usage.get("cache_creation_input_tokens", 0)
    parts = [f"{in_t:,} in", f"{out_t:,} out"]
    if cache_r:
        parts.append(f"{cache_r:,} cache read")
    if cache_w:
        parts.append(f"{cache_w:,} cache write")
    return " · ".join(parts)


_FATAL_ERRORS = [
    "credit balance is too low",
    "invalid api key",
    "authentication error",
    "account has been disabled",
]


def _is_fatal_error(text: str) -> bool:
    """Check if a text block contains a fatal error that should stop the agent."""
    lower = text.strip().lower()
    return any(err in lower for err in _FATAL_ERRORS)


def _strip_workspace(path: str, cwd: str | None) -> str:
    """Strip the workspace temp dir prefix from a file path for readability.

    On macOS, tempfile returns /var/folders/... but tools resolve the symlink
    to /private/var/folders/..., so we try both the original cwd and its
    realpath to ensure the prefix is stripped.
    """
    if not cwd:
        return path
    for prefix in (cwd, os.path.realpath(cwd)):
        if path.startswith(prefix):
            return path[len(prefix) :].lstrip("/")
    return path


def _tool_summary(block: ToolUseBlock, cwd: str | None = None) -> str:
    """One-line summary of what a tool call is doing."""
    inp = block.input
    match block.name:
        case "Read":
            return _strip_workspace(inp.get("file_path", ""), cwd)
        case "Write" | "Edit":
            return _strip_workspace(inp.get("file_path", ""), cwd)
        case "Glob":
            return inp.get("pattern", "")
        case "Grep":
            path = _strip_workspace(inp.get("path", "."), cwd)
            return f"{inp.get('pattern', '')} in {path}"
        case "Bash":
            cmd = inp.get("command", "")
            return cmd if len(cmd) <= 120 else cmd + "…"
        case "Task":
            return inp.get("description", inp.get("prompt", ""))
        case "WebFetch":
            return inp.get("url", "")
        case "WebSearch":
            return inp.get("query", "")
        case _:
            return str(inp) if inp else ""


def _extract_json(text: str) -> str:
    """Strip markdown code-block wrapping from a JSON string."""
    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    return text.strip()
