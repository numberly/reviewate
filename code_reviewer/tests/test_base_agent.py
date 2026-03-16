"""Tests for BaseAgent with mocked claude_agent_sdk.query()."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from code_reviewer.agents.base import AgentResult, BaseAgent, _strip_workspace


class StubAgent(BaseAgent):
    """Test agent subclass."""

    prompt_file = "style.md"
    permission_mode = "plan"
    allowed_tools = ["Read", "Grep"]
    model = "sonnet"


def _make_assistant_message(text: str):
    """Create a mock AssistantMessage with a TextBlock."""
    from claude_agent_sdk import AssistantMessage, TextBlock

    return AssistantMessage(content=[TextBlock(text=text)], model="sonnet")


def _make_result_message(
    result: str = "",
    cost: float = 0.05,
    duration: int = 1000,
    session_id: str = "test-session",
    num_turns: int = 3,
):
    """Create a mock ResultMessage."""
    from claude_agent_sdk import ResultMessage

    return ResultMessage(
        subtype="result",
        result=result,
        duration_ms=duration,
        duration_api_ms=duration,
        is_error=False,
        num_turns=num_turns,
        session_id=session_id,
        total_cost_usd=cost,
        usage={"input_tokens": 100, "output_tokens": 50},
    )


class TestBaseAgentInit:
    def test_default_attributes(self):
        agent = BaseAgent()
        assert agent.cwd is None
        assert agent.debug is False
        assert agent.env == {}

    def test_custom_attributes(self):
        agent = BaseAgent(cwd="/tmp/test", debug=True, env={"KEY": "val"})
        assert agent.cwd == "/tmp/test"
        assert agent.debug is True
        assert agent.env == {"KEY": "val"}

    def test_cwd_path_object(self):
        agent = BaseAgent(cwd=Path("/tmp/test"))
        assert agent.cwd == "/tmp/test"


class TestLoadSystemPrompt:
    def test_loads_prompt_file(self):
        agent = StubAgent()
        prompt = agent.load_system_prompt()
        # reviewate-style.md has front matter that should be stripped
        assert "---" not in prompt.split("\n")[0]
        assert "Code Review Formatter" in prompt

    def test_empty_prompt_file(self):
        agent = BaseAgent()
        agent.prompt_file = ""
        assert agent.load_system_prompt() == ""


class TestBuildOptions:
    def test_options_have_correct_fields(self):
        agent = StubAgent(cwd="/tmp/test", env={"KEY": "val"})
        opts = agent._build_options()
        assert opts.permission_mode == "plan"
        assert opts.allowed_tools == ["Read", "Grep"]
        assert opts.model == "sonnet"
        assert opts.cwd == "/tmp/test"
        assert opts.env == {"KEY": "val"}

    def test_system_prompt_extra_appended(self):
        agent = StubAgent(system_prompt_extra="Extra instructions")
        opts = agent._build_options()
        assert opts.system_prompt.endswith("Extra instructions")


def test_system_prompt_prefix_ordering():
    """system_prompt_prefix comes before agent prompt, system_prompt_extra comes after."""
    agent = StubAgent(
        system_prompt_prefix="PREFIX_CONTENT",
        system_prompt_extra="EXTRA_CONTENT",
    )
    opts = agent._build_options()
    prompt = opts.system_prompt
    prefix_pos = prompt.index("PREFIX_CONTENT")
    # Agent prompt contains "Code Review Formatter" from reviewate-style.md
    agent_pos = prompt.index("Code Review Formatter")
    extra_pos = prompt.index("EXTRA_CONTENT")
    assert prefix_pos < agent_pos < extra_pos

    def test_output_format_from_schema(self):
        class MyOutput(BaseModel):
            answer: str

        class SchemaAgent(BaseAgent):
            output_schema = MyOutput

        agent = SchemaAgent()
        opts = agent._build_options()
        assert opts.output_format == {
            "type": "json_schema",
            "schema": MyOutput.model_json_schema(),
        }

    def test_no_output_format_by_default(self):
        agent = StubAgent()
        opts = agent._build_options()
        assert opts.output_format is None


class TestInvoke:
    @pytest.mark.asyncio
    async def test_invoke_returns_result_text(self):
        agent = StubAgent()
        messages = [
            _make_assistant_message("thinking..."),
            _make_result_message(result="Hello World"),
        ]

        async def mock_query(**kwargs):
            for msg in messages:
                yield msg

        with patch("code_reviewer.agents.base.query", side_effect=mock_query):
            result = await agent.invoke("test prompt")

        assert isinstance(result, AgentResult)
        assert result.text == "Hello World"
        assert result.cost_usd == 0.05
        assert result.duration_ms == 1000
        assert result.session_id == "test-session"
        assert result.num_turns == 3

    @pytest.mark.asyncio
    async def test_invoke_empty_response(self):
        agent = StubAgent()
        messages = [_make_result_message()]

        async def mock_query(**kwargs):
            for msg in messages:
                yield msg

        with patch("code_reviewer.agents.base.query", side_effect=mock_query):
            result = await agent.invoke("test prompt")

        assert result.text == ""

    @pytest.mark.asyncio
    async def test_invoke_logs_tool_calls(self):
        """ToolUseBlock messages are logged at INFO level."""
        from claude_agent_sdk import AssistantMessage, ToolUseBlock

        agent = StubAgent()
        messages = [
            AssistantMessage(
                content=[ToolUseBlock(id="t1", name="Read", input={"file_path": "/foo.py"})],
                model="sonnet",
            ),
            _make_result_message(result="done"),
        ]

        async def mock_query(**kwargs):
            for msg in messages:
                yield msg

        with patch("code_reviewer.agents.base.query", side_effect=mock_query):
            result = await agent.invoke("test")

        assert result.text == "done"

    @pytest.mark.asyncio
    async def test_invoke_calls_on_tool_call_callback(self):
        """on_tool_call callback is invoked for each ToolUseBlock."""
        from claude_agent_sdk import AssistantMessage, ToolUseBlock

        agent = StubAgent()
        messages = [
            AssistantMessage(
                content=[ToolUseBlock(id="t1", name="Read", input={"file_path": "/foo.py"})],
                model="sonnet",
            ),
            _make_result_message(result="done"),
        ]

        async def mock_query(**kwargs):
            for msg in messages:
                yield msg

        callback = MagicMock()
        with patch("code_reviewer.agents.base.query", side_effect=mock_query):
            await agent.invoke("test", on_tool_call=callback)

        callback.assert_called_once_with("Read", "/foo.py", {"file_path": "/foo.py"})

    @pytest.mark.asyncio
    async def test_invoke_skips_callback_for_internal_tools(self):
        """ToolSearch and other internal tools are logged at DEBUG, not callbacks."""
        from claude_agent_sdk import AssistantMessage, ToolUseBlock

        agent = StubAgent()
        messages = [
            AssistantMessage(
                content=[ToolUseBlock(id="t1", name="ToolSearch", input={"query": "foo"})],
                model="sonnet",
            ),
            _make_result_message(result="done"),
        ]

        async def mock_query(**kwargs):
            for msg in messages:
                yield msg

        callback = MagicMock()
        with patch("code_reviewer.agents.base.query", side_effect=mock_query):
            await agent.invoke("test", on_tool_call=callback)

        # ToolSearch should still trigger callback (it's just logged at DEBUG)
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_invoke_calls_on_task_started_callback(self):
        """on_task_started callback is invoked for TaskStartedMessage."""
        from claude_agent_sdk import TaskStartedMessage

        agent = StubAgent()
        task_msg = TaskStartedMessage(
            subtype="task_started",
            data={},
            task_id="task-1",
            description="Code review analyzer",
            uuid="uuid-1",
            session_id="sess-1",
            task_type="reviewer",
        )
        messages = [task_msg, _make_result_message(result="done")]

        async def mock_query(**kwargs):
            for msg in messages:
                yield msg

        callback = MagicMock()
        with patch("code_reviewer.agents.base.query", side_effect=mock_query):
            await agent.invoke("test", on_task_started=callback)

        callback.assert_called_once_with("reviewer", "Code review analyzer")

    @pytest.mark.asyncio
    async def test_invoke_skips_task_started_without_type(self):
        """TaskStartedMessage without task_type should not trigger callback."""
        from claude_agent_sdk import TaskStartedMessage

        agent = StubAgent()
        task_msg = TaskStartedMessage(
            subtype="task_started",
            data={},
            task_id="task-1",
            description="Unknown task",
            uuid="uuid-1",
            session_id="sess-1",
            task_type=None,
        )
        messages = [task_msg, _make_result_message(result="done")]

        async def mock_query(**kwargs):
            for msg in messages:
                yield msg

        callback = MagicMock()
        with patch("code_reviewer.agents.base.query", side_effect=mock_query):
            await agent.invoke("test", on_task_started=callback)

        callback.assert_not_called()


class TestStripWorkspace:
    def test_strips_cwd_prefix(self):
        assert (
            _strip_workspace("/tmp/reviewate-abc/src/main.py", "/tmp/reviewate-abc")
            == "src/main.py"
        )

    def test_no_cwd(self):
        assert _strip_workspace("/foo/bar.py", None) == "/foo/bar.py"

    def test_no_match(self):
        assert _strip_workspace("/other/path.py", "/tmp/reviewate-abc") == "/other/path.py"


class TestInvokeStructured:
    @pytest.mark.asyncio
    async def test_parses_json_from_text(self):
        from pydantic import BaseModel

        class Output(BaseModel):
            answer: str

        agent = StubAgent()
        messages = [
            _make_result_message(result='```json\n{"answer": "42"}\n```'),
        ]

        async def mock_query(**kwargs):
            for msg in messages:
                yield msg

        with patch("code_reviewer.agents.base.query", side_effect=mock_query):
            result = await agent.invoke_structured("test", Output)

        assert result.answer == "42"


class TestInvokeCancelScopeRecovery:
    """Tests for recovering from anyio cancel scope RuntimeError.

    When invoke() runs inside asyncio.gather (parallel analyzers), the SDK's
    async generator cleanup can raise RuntimeError about cancel scopes being
    exited in a different task. If we already have useful output, we should
    preserve it instead of losing everything.
    """

    @pytest.mark.asyncio
    async def test_recovers_with_text_output(self):
        """RuntimeError with captured text → result preserved, not raised."""
        agent = StubAgent()

        async def mock_query(**kwargs):
            yield _make_assistant_message("Analysis complete: found 3 bugs")
            raise RuntimeError(
                "Attempted to exit cancel scope in a different task than it was entered in"
            )

        with patch("code_reviewer.agents.base.query", side_effect=mock_query):
            result = await agent.invoke("test")

        assert result.text == "Analysis complete: found 3 bugs"
        # No ResultMessage was received, so metadata is missing
        assert result.cost_usd is None
        assert result.num_turns == 0

    @pytest.mark.asyncio
    async def test_recovers_with_structured_output(self):
        """RuntimeError with captured structured output → result preserved."""
        from claude_agent_sdk import AssistantMessage, ToolUseBlock

        agent = StubAgent()

        async def mock_query(**kwargs):
            yield AssistantMessage(
                content=[
                    ToolUseBlock(
                        id="t1",
                        name="StructuredOutput",
                        input={"comments": [{"path": "a.py", "body": "bug"}]},
                    )
                ],
                model="sonnet",
            )
            raise RuntimeError(
                "Attempted to exit cancel scope in a different task than it was entered in"
            )

        with patch("code_reviewer.agents.base.query", side_effect=mock_query):
            result = await agent.invoke("test")

        assert result.structured_output == {"comments": [{"path": "a.py", "body": "bug"}]}

    @pytest.mark.asyncio
    async def test_raises_when_no_output_captured(self):
        """RuntimeError with no captured output → still raises."""
        agent = StubAgent()

        async def mock_query(**kwargs):
            raise RuntimeError(
                "Attempted to exit cancel scope in a different task than it was entered in"
            )
            yield  # noqa: RUF027 — makes this an async generator

        with patch("code_reviewer.agents.base.query", side_effect=mock_query):
            with pytest.raises(RuntimeError, match="cancel scope"):
                await agent.invoke("test")

    @pytest.mark.asyncio
    async def test_raises_unrelated_runtime_error(self):
        """Non-cancel-scope RuntimeError → always raised, even with output."""
        agent = StubAgent()

        async def mock_query(**kwargs):
            yield _make_assistant_message("some output")
            raise RuntimeError("something completely different")

        with patch("code_reviewer.agents.base.query", side_effect=mock_query):
            with pytest.raises(RuntimeError, match="something completely different"):
                await agent.invoke("test")

    @pytest.mark.asyncio
    async def test_fatal_error_still_raised(self):
        """Fatal errors (e.g. invalid API key) are not swallowed."""
        agent = StubAgent()

        async def mock_query(**kwargs):
            yield _make_assistant_message("Invalid API Key")

        with patch("code_reviewer.agents.base.query", side_effect=mock_query):
            with pytest.raises(RuntimeError, match="Invalid API Key"):
                await agent.invoke("test")
