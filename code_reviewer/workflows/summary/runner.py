"""Summary workflow — Python-driven pipeline with structured output and posting."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from jinja2 import Template
from pydantic import BaseModel

from code_reviewer.agents.issue_explorer import IssueExplorerAgent, IssueExplorerOutput
from code_reviewer.agents.summary import SummarizerAgent
from code_reviewer.agents.summary_parser import SummaryParserAgent
from code_reviewer.workflows.context import RunContext
from code_reviewer.workflows.summary.schema import ParsedSummaryOutput, SummaryOutput

logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path(__file__).parent.parent.parent / "prompts" / "summary-template.md"


class _SummaryComment(BaseModel):
    """Minimal model for posting a summary comment via handler."""

    body: str


async def run_summary(ctx: RunContext) -> None:
    """Run the summary workflow: issue explore -> summarize -> parse -> format -> post."""
    logger.info("Starting summary workflow")

    repo_dir = os.path.join(ctx.workspace, ctx.repo.split("/")[-1])
    base_kwargs: dict = {
        "cwd": repo_dir,
        "debug": ctx.debug,
        "env": ctx.agent_env,
        "system_prompt_extra": ctx.system_extra,
    }
    total_cost = 0.0

    # Step 1: Explore linked issues
    if ctx.tracker:
        ctx.tracker.step("Exploring linked issues...")

    issue_explorer = IssueExplorerAgent(
        model=ctx.utility_model,
        platform=ctx.handler.platform_name,
        repo=ctx.repo,
        pr_description=ctx.pr_body,
        **base_kwargs,
    )
    issue_cb = ctx.tracker.make_tool_callback() if ctx.tracker else None
    issue_result = await issue_explorer.invoke(
        f"Explore linked issues for {ctx.target}", on_tool_call=issue_cb
    )
    total_cost += issue_result.cost_usd or 0
    ctx.add_usage(issue_result.usage, "IssueExplorer")
    if ctx.tracker:
        ctx.tracker.done("", usage=issue_result.usage)

    issue_output = _parse_structured(issue_result.structured_output, IssueExplorerOutput)
    issue_context = issue_output.context if issue_output else issue_result.text.strip()
    issue_refs = issue_output.issue_refs if issue_output else []
    has_issue_context = issue_context and issue_context != "No linked issues found."
    if has_issue_context:
        logger.info("Issue context found for summary (refs: %s)", issue_refs)

    # Step 2: Summarize
    if ctx.tracker:
        ctx.tracker.step("Summarizing changes...")

    summarizer = SummarizerAgent(
        model=ctx.utility_model,
        pr_description=ctx.pr_body,
        diff=ctx.diff_text,
        issue_context=issue_context if has_issue_context else "",
        **base_kwargs,
    )
    summarize_result = await summarizer.invoke("Summarize the PR changes.")
    total_cost += summarize_result.cost_usd or 0
    ctx.add_usage(summarize_result.usage, "Summarizer")
    if ctx.tracker:
        ctx.tracker.done("", usage=summarize_result.usage)

    summary_output = _parse_structured(summarize_result.structured_output, SummaryOutput)
    if summary_output is None:
        summary_output = SummaryOutput(description=summarize_result.text.strip())
    logger.info("Summary generated (%d chars)", len(summary_output.description))

    # Step 3: Parse/refine summary
    if ctx.tracker:
        ctx.tracker.step("Refining summary...")

    parser_input = json.dumps(summary_output.model_dump())
    parser = SummaryParserAgent(model=ctx.utility_model, **base_kwargs)
    parse_result = await parser.invoke(parser_input)
    total_cost += parse_result.cost_usd or 0
    ctx.add_usage(parse_result.usage, "SummaryParser")
    if ctx.tracker:
        ctx.tracker.done("", usage=parse_result.usage)

    parsed_output = _parse_structured(parse_result.structured_output, ParsedSummaryOutput)
    if parsed_output is None:
        parsed_output = ParsedSummaryOutput(description=summary_output.description)
    logger.info("Summary refined (%d chars)", len(parsed_output.description))

    # Step 4: Format with template
    summary_body = _format_summary(parsed_output.description, issue_refs)
    ctx.summary_body = summary_body
    logger.info("Summary formatted (%d chars)", len(summary_body))
    logger.debug("Final summary:\n%s", summary_body)

    # Step 5: Post or dry run
    if ctx.dry_run:
        logger.info("Dry run: skipping post of summary")
    else:
        if ctx.tracker:
            ctx.tracker.step("Posting summary...")
        comment = _SummaryComment(body=summary_body)
        posted = ctx.handler.post_regular_comment(comment, ctx.repo, ctx.pr, ctx.sub_env)
        if posted:
            logger.info("Summary posted successfully")
        else:
            logger.warning("Failed to post summary")

    ctx.total_cost += total_cost

    if ctx.tracker:
        detail = "summary complete"
        if ctx.dry_run:
            detail += " (dry run)"
        ctx.tracker.done(detail)
    ctx.result_data["workflows"].append({"name": "summary"})


def _parse_structured[T: BaseModel](structured_output: object, model: type[T]) -> T | None:
    """Parse structured output from an agent result, returning None on failure."""
    if structured_output is None:
        return None
    try:
        return model.model_validate(structured_output)
    except Exception:
        logger.debug("Failed to parse structured output as %s", model.__name__)
        return None


def _format_summary(description: str, issue_refs: list[str]) -> str:
    """Render the summary template with description and issue references."""
    template_str = TEMPLATE_PATH.read_text()
    template = Template(template_str)
    return template.render(description=description, issue_refs=issue_refs)
