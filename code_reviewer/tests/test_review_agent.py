"""Tests for pipeline agents, extract_comments, and structured output helpers."""

import json
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from code_reviewer.adaptors.repository.github.schema import GitHubReviewComment
from code_reviewer.adaptors.repository.gitlab.schema import GitLabReviewComment
from code_reviewer.adaptors.repository.schema import Review
from code_reviewer.agents.analyzer import AnalyzeAgent
from code_reviewer.agents.base import AgentResult
from code_reviewer.agents.deduplicator import DedupAgent
from code_reviewer.agents.fact_checker import FactCheckAgent
from code_reviewer.agents.issue_explorer import IssueExplorerAgent
from code_reviewer.agents.styler import StyleAgent
from code_reviewer.agents.summary import SummarizerAgent
from code_reviewer.agents.summary_parser import SummaryParserAgent
from code_reviewer.agents.synthesizer import SynthesizerAgent
from code_reviewer.workflows.review.schema import FilterResult, StyleResult
from code_reviewer.workflows.review.utils import (
    _apply_filter,
    _apply_style,
    extract_comments,
)
from code_reviewer.workflows.summary.schema import ParsedSummaryOutput, SummaryOutput


class TestExtractComments:
    def test_extracts_from_code_block_github(self):
        text = '```json\n{"comments": [{"path": "a.py", "line": 1, "body": "B"}]}\n```'
        comments = extract_comments(text, GitHubReviewComment)
        assert len(comments) == 1
        assert isinstance(comments[0], GitHubReviewComment)
        assert comments[0].path == "a.py"
        assert comments[0].line == 1

    def test_extracts_from_code_block_gitlab(self):
        text = '```json\n{"comments": [{"new_path": "a.py", "new_line": 1, "body": "B"}]}\n```'
        comments = extract_comments(text, GitLabReviewComment)
        assert len(comments) == 1
        assert isinstance(comments[0], GitLabReviewComment)
        assert comments[0].new_path == "a.py"
        assert comments[0].new_line == 1

    def test_extracts_from_raw_json(self):
        text = 'Here are the comments:\n[{"new_path": "b.py", "body": "Y"}]'
        comments = extract_comments(text, GitLabReviewComment)
        assert len(comments) == 1
        assert comments[0].new_path == "b.py"

    def test_returns_empty_for_no_json(self):
        assert extract_comments("No issues found.", GitHubReviewComment) == []

    def test_returns_empty_for_empty_array(self):
        assert extract_comments("[]", GitHubReviewComment) == []

    def test_skips_invalid_items(self):
        raw = json.dumps(
            [
                {"path": "a.py", "line": 1, "body": "B"},
                {"invalid": "item"},
            ]
        )
        comments = extract_comments(f"```json\n{raw}\n```", GitHubReviewComment)
        assert len(comments) == 1

    def test_returns_empty_for_non_array(self):
        assert extract_comments('{"not": "an array"}', GitHubReviewComment) == []

    def test_multiple_comments(self):
        raw = json.dumps(
            [
                {"path": "a.py", "line": 1, "body": "B1"},
                {"path": "b.py", "line": 2, "body": "B2"},
                {"path": "c.py", "body": "B3"},
            ]
        )
        comments = extract_comments(raw, GitHubReviewComment)
        assert len(comments) == 3


class TestAnalyzeAgent:
    def test_tools(self):
        agent = AnalyzeAgent(cwd="/tmp")
        assert "Read" in agent.allowed_tools
        assert "Grep" in agent.allowed_tools
        assert "Glob" in agent.allowed_tools
        assert "Bash" in agent.allowed_tools

    def test_model_default(self):
        agent = AnalyzeAgent(cwd="/tmp")
        assert agent.model == "sonnet"

    def test_model_override(self):
        agent = AnalyzeAgent(model="opus", cwd="/tmp")
        assert agent.model == "opus"

    def test_no_subagents(self):
        agent = AnalyzeAgent(cwd="/tmp")
        assert agent.agents is None

    def test_permission_mode(self):
        agent = AnalyzeAgent(cwd="/tmp")
        assert agent.permission_mode == "bypassPermissions"

    def test_output_schema_set(self):
        schema = Review[GitHubReviewComment]
        agent = AnalyzeAgent(output_schema=schema, cwd="/tmp")
        assert agent.output_schema is schema

    def test_platform_in_template_vars(self):
        agent = AnalyzeAgent(platform="gitlab", cwd="/tmp")
        assert agent.template_vars["platform"] == "gitlab"

    def test_platform_default(self):
        agent = AnalyzeAgent(cwd="/tmp")
        assert agent.template_vars["platform"] == "github"

    @pytest.mark.asyncio
    async def test_invoke(self):
        agent = AnalyzeAgent(cwd="/tmp")

        async def mock_query(**kwargs):
            from claude_agent_sdk import ResultMessage

            yield ResultMessage(
                subtype="success",
                result="**[HIGH] Bug in foo**\n\n- **File**: `a.py:10`",
                duration_ms=1000,
                duration_api_ms=1000,
                is_error=False,
                num_turns=3,
                session_id="test",
                total_cost_usd=0.05,
                usage={"input_tokens": 100, "output_tokens": 50},
            )

        with patch("code_reviewer.agents.base.query", side_effect=mock_query):
            result = await agent.invoke("Review owner/repo PR #1")

        assert "Bug in foo" in result.text
        assert result.cost_usd == 0.05


class TestDedupAgent:
    def test_no_tools(self):
        agent = DedupAgent(cwd="/tmp")
        assert agent.allowed_tools == []

    def test_max_turns(self):
        agent = DedupAgent(cwd="/tmp")
        assert agent.max_turns == 1

    def test_model_default(self):
        agent = DedupAgent(cwd="/tmp")
        assert agent.model == "haiku"

    def test_discussions_in_template_vars(self):
        discussions = [{"author": "user", "body": "fix this"}]
        agent = DedupAgent(discussions=discussions, cwd="/tmp")
        assert agent.template_vars["discussions"] == discussions

    def test_empty_discussions(self):
        agent = DedupAgent(discussions=None, cwd="/tmp")
        assert agent.template_vars["discussions"] == []

    def test_permission_mode(self):
        agent = DedupAgent(cwd="/tmp")
        assert agent.permission_mode == "bypassPermissions"

    def test_output_schema_is_filter_result(self):
        agent = DedupAgent(cwd="/tmp")
        assert agent.output_schema is FilterResult


class TestIssueExplorerAgent:
    def test_tools(self):
        agent = IssueExplorerAgent(cwd="/tmp")
        assert agent.allowed_tools == ["Bash"]

    def test_model_default(self):
        agent = IssueExplorerAgent(cwd="/tmp")
        assert agent.model == "haiku"

    def test_permission_mode(self):
        agent = IssueExplorerAgent(cwd="/tmp")
        assert agent.permission_mode == "bypassPermissions"


class TestSynthesizerAgent:
    def test_no_tools(self):
        agent = SynthesizerAgent(cwd="/tmp")
        assert agent.allowed_tools == []

    def test_max_turns(self):
        agent = SynthesizerAgent(cwd="/tmp")
        assert agent.max_turns == 1

    def test_model_default(self):
        agent = SynthesizerAgent(cwd="/tmp")
        assert agent.model == "haiku"

    def test_permission_mode(self):
        agent = SynthesizerAgent(cwd="/tmp")
        assert agent.permission_mode == "bypassPermissions"

    def test_no_subagents(self):
        agent = SynthesizerAgent(cwd="/tmp")
        assert agent.agents is None

    def test_output_schema_set(self):
        schema = Review[GitHubReviewComment]
        agent = SynthesizerAgent(output_schema=schema, cwd="/tmp")
        assert agent.output_schema is schema

    def test_platform_in_template_vars(self):
        agent = SynthesizerAgent(platform="gitlab", cwd="/tmp")
        assert agent.template_vars["platform"] == "gitlab"

    def test_platform_default(self):
        agent = SynthesizerAgent(cwd="/tmp")
        assert agent.template_vars["platform"] == "github"


class TestFactCheckAgent:
    def test_tools(self):
        agent = FactCheckAgent(cwd="/tmp")
        assert "Read" in agent.allowed_tools
        assert "Grep" in agent.allowed_tools
        assert "Glob" in agent.allowed_tools
        assert "Bash" in agent.allowed_tools
        assert "Skill" in agent.allowed_tools

    def test_model_default(self):
        agent = FactCheckAgent(cwd="/tmp")
        assert agent.model == "sonnet"

    def test_model_override(self):
        agent = FactCheckAgent(model="opus", cwd="/tmp")
        assert agent.model == "opus"

    def test_no_subagents(self):
        agent = FactCheckAgent(cwd="/tmp")
        assert agent.agents is None

    def test_permission_mode(self):
        agent = FactCheckAgent(cwd="/tmp")
        assert agent.permission_mode == "bypassPermissions"

    def test_output_schema_is_filter_result(self):
        agent = FactCheckAgent(cwd="/tmp")
        assert agent.output_schema is FilterResult


class TestStyleAgent:
    def test_no_tools(self):
        agent = StyleAgent(cwd="/tmp")
        assert agent.allowed_tools == []

    def test_max_turns(self):
        agent = StyleAgent(cwd="/tmp")
        assert agent.max_turns == 1

    def test_model_default(self):
        agent = StyleAgent(cwd="/tmp")
        assert agent.model == "haiku"

    def test_output_schema_is_style_result(self):
        agent = StyleAgent(cwd="/tmp")
        assert agent.output_schema is StyleResult

    def test_platform_in_template_vars(self):
        agent = StyleAgent(platform="gitlab", cwd="/tmp")
        assert agent.template_vars["platform"] == "gitlab"

    def test_platform_default(self):
        agent = StyleAgent(cwd="/tmp")
        assert agent.template_vars["platform"] == "github"

    @pytest.mark.asyncio
    async def test_invoke_structured_output(self):
        agent = StyleAgent(platform="github", cwd="/tmp")

        async def mock_query(**kwargs):
            from claude_agent_sdk import ResultMessage

            msg = ResultMessage(
                subtype="success",
                result="",
                duration_ms=500,
                duration_api_ms=500,
                is_error=False,
                num_turns=1,
                session_id="test",
                total_cost_usd=0.01,
                usage={"input_tokens": 100, "output_tokens": 50},
            )
            msg.structured_output = {
                "bodies": ["**[Bug] T**\n\n- **Problem:** B\n- **Fix:** F"],
            }
            yield msg

        with patch("code_reviewer.agents.base.query", side_effect=mock_query):
            result = await agent.invoke("Style these findings")

        assert result.structured_output is not None
        sr = StyleResult.model_validate(result.structured_output)
        assert len(sr.bodies) == 1
        assert "**[Bug] T**" in sr.bodies[0]


class TestFilterResult:
    def test_valid(self):
        fr = FilterResult(keep_indices=[0, 2, 5])
        assert fr.keep_indices == [0, 2, 5]

    def test_empty(self):
        fr = FilterResult(keep_indices=[])
        assert fr.keep_indices == []

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            FilterResult(keep_indices=[0], extra="bad")

    def test_apply_filter_structured(self):
        comments = [
            GitHubReviewComment(path="a.py", line=1, body="A"),
            GitHubReviewComment(path="b.py", line=2, body="B"),
            GitHubReviewComment(path="c.py", line=3, body="C"),
        ]
        result = AgentResult(text="", structured_output={"keep_indices": [0, 2]})
        filtered = _apply_filter(comments, result)
        assert len(filtered) == 2
        assert filtered[0].path == "a.py"
        assert filtered[1].path == "c.py"

    def test_apply_filter_out_of_bounds_ignored(self):
        comments = [GitHubReviewComment(path="a.py", line=1, body="A")]
        result = AgentResult(text="", structured_output={"keep_indices": [0, 5]})
        filtered = _apply_filter(comments, result)
        assert len(filtered) == 1

    def test_apply_filter_fallback_text(self):
        comments = [
            GitHubReviewComment(path="a.py", line=1, body="A"),
            GitHubReviewComment(path="b.py", line=2, body="B"),
        ]
        result = AgentResult(text='{"keep_indices": [1]}', structured_output=None)
        filtered = _apply_filter(comments, result)
        assert len(filtered) == 1
        assert filtered[0].path == "b.py"

    def test_apply_filter_fallback_keeps_all(self):
        comments = [GitHubReviewComment(path="a.py", line=1, body="A")]
        result = AgentResult(text="no json here", structured_output=None)
        filtered = _apply_filter(comments, result)
        assert len(filtered) == 1


class TestStyleResult:
    def test_valid(self):
        sr = StyleResult(bodies=["body1", "body2"])
        assert sr.bodies == ["body1", "body2"]

    def test_empty(self):
        sr = StyleResult(bodies=[])
        assert sr.bodies == []

    def test_apply_style_structured(self):
        comments = [
            GitHubReviewComment(path="a.py", line=1, body="old A"),
            GitHubReviewComment(path="b.py", line=2, body="old B"),
        ]
        result = AgentResult(text="", structured_output={"bodies": ["new A", "new B"]})
        styled = _apply_style(comments, result)
        assert len(styled) == 2
        assert styled[0].body == "new A"
        assert styled[0].path == "a.py"  # preserved
        assert styled[1].body == "new B"
        assert styled[1].line == 2  # preserved

    def test_apply_style_count_mismatch_keeps_originals(self):
        comments = [GitHubReviewComment(path="a.py", line=1, body="old")]
        result = AgentResult(text="", structured_output={"bodies": ["new A", "new B"]})
        styled = _apply_style(comments, result)
        assert len(styled) == 1
        assert styled[0].body == "old"

    def test_apply_style_no_structured_keeps_originals(self):
        comments = [GitHubReviewComment(path="a.py", line=1, body="old")]
        result = AgentResult(text="no json", structured_output=None)
        styled = _apply_style(comments, result)
        assert len(styled) == 1
        assert styled[0].body == "old"


class TestSummarizerAgent:
    def test_no_tools(self):
        agent = SummarizerAgent(cwd="/tmp")
        assert agent.allowed_tools == []

    def test_max_turns(self):
        agent = SummarizerAgent(cwd="/tmp")
        assert agent.max_turns == 1

    def test_model_default(self):
        agent = SummarizerAgent(cwd="/tmp")
        assert agent.model == "haiku"

    def test_model_override(self):
        agent = SummarizerAgent(model="sonnet", cwd="/tmp")
        assert agent.model == "sonnet"

    def test_permission_mode(self):
        agent = SummarizerAgent(cwd="/tmp")
        assert agent.permission_mode == "bypassPermissions"

    def test_output_schema_is_summary_output(self):
        agent = SummarizerAgent(cwd="/tmp")
        assert agent.output_schema is SummaryOutput

    def test_prompt_file(self):
        agent = SummarizerAgent(cwd="/tmp")
        assert agent.prompt_file == "summarizer.md"


class TestSummaryParserAgent:
    def test_no_tools(self):
        agent = SummaryParserAgent(cwd="/tmp")
        assert agent.allowed_tools == []

    def test_max_turns(self):
        agent = SummaryParserAgent(cwd="/tmp")
        assert agent.max_turns == 1

    def test_model_default(self):
        agent = SummaryParserAgent(cwd="/tmp")
        assert agent.model == "haiku"

    def test_model_override(self):
        agent = SummaryParserAgent(model="sonnet", cwd="/tmp")
        assert agent.model == "sonnet"

    def test_permission_mode(self):
        agent = SummaryParserAgent(cwd="/tmp")
        assert agent.permission_mode == "bypassPermissions"

    def test_output_schema_is_parsed_summary_output(self):
        agent = SummaryParserAgent(cwd="/tmp")
        assert agent.output_schema is ParsedSummaryOutput

    def test_prompt_file(self):
        agent = SummaryParserAgent(cwd="/tmp")
        assert agent.prompt_file == "summary-parser.md"


class TestSummaryOutput:
    def test_valid(self):
        so = SummaryOutput(description="- Change 1\n- Change 2")
        assert so.description == "- Change 1\n- Change 2"

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            SummaryOutput(description="test", extra="bad")


class TestParsedSummaryOutput:
    def test_valid(self):
        pso = ParsedSummaryOutput(description="- Refined change")
        assert pso.description == "- Refined change"

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            ParsedSummaryOutput(description="test", extra="bad")
