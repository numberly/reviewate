"""Review workflow — Python-driven pipeline with guardrail and posting."""

from __future__ import annotations

import asyncio
import logging
import os

from code_reviewer.agents.analyzer import AnalyzeAgent
from code_reviewer.agents.base import AgentResult
from code_reviewer.agents.deduplicator import DedupAgent
from code_reviewer.agents.fact_checker import FactCheckAgent
from code_reviewer.agents.issue_explorer import IssueExplorerAgent
from code_reviewer.agents.styler import StyleAgent
from code_reviewer.agents.synthesizer import SynthesizerAgent
from code_reviewer.workflows.context import RunContext
from code_reviewer.workflows.review.schema import LgtmComment, ReviewResult
from code_reviewer.workflows.review.utils import (
    _apply_filter,
    _apply_guardrail,
    _apply_style,
    _empty_result,
    _is_empty_result,
    _parse_review_output,
    _post_with_retry,
    _serialize_comments,
    _serialize_numbered,
)

logger = logging.getLogger(__name__)


async def run_review(ctx: RunContext) -> None:
    """Run the review workflow: pipeline -> guardrail -> post."""
    logger.info("Starting review workflow")

    review_result = await _run_pipeline(ctx)
    if review_result.cost_usd:
        ctx.total_cost += review_result.cost_usd

    comments = review_result.comments
    review = review_result.review
    logger.info("Review returned %d comments", len(comments))

    if comments and not ctx.dry_run:
        review, comments = _apply_guardrail(review, comments)

    ctx.review_comments = list(comments)

    if comments and not ctx.dry_run:
        if ctx.tracker:
            ctx.tracker.step("Posting comments...")
        posted = await _post_with_retry(ctx, review)
        logger.info("Posted %d/%d comments", posted, len(comments))
    elif not comments and not ctx.dry_run:
        if ctx.tracker:
            ctx.tracker.step("Posting LGTM...")
        ctx.handler.post_regular_comment(LgtmComment(), ctx.repo, ctx.pr, ctx.sub_env)
        logger.info("No issues found — posted LGTM comment")

    if ctx.tracker:
        detail = f"{len(comments)} comments"
        if ctx.dry_run:
            detail += " (dry run)"
        ctx.tracker.done(detail)

    ctx.result_data["workflows"].append({"name": "review"})
    ctx.result_data["comments_count"] = len(comments)
    ctx.result_data["comments"] = [c.model_dump() for c in comments]


async def _run_pipeline(ctx: RunContext) -> ReviewResult:
    """Run the Python-driven review pipeline.

    Steps:
        1a: IssueExplorerAgent -> linked issue context (text)
        1b: asyncio.gather(AnalyzeAgent x 2) -> Review[Comment] each -> merge
        2: SynthesizerAgent -> Review[Comment] (deduplicated)
        3: DedupAgent (if discussions) -> FilterResult(keep_indices)
        4: FactCheckAgent -> FilterResult(keep_indices)
        5: StyleAgent -> StyleResult(bodies) -> apply to comments
    """
    repo_dir = os.path.join(ctx.workspace, ctx.repo.split("/")[-1])
    platform = ctx.handler.platform_name
    review_cls = ctx.handler.review_schema
    comment_cls = ctx.handler.comment_model

    base_prompt = f"Review {ctx.target}"

    base_kwargs: dict = {
        "cwd": repo_dir,
        "debug": ctx.debug,
        "env": ctx.agent_env,
        "system_prompt_extra": ctx.system_extra,
    }
    total_cost = 0.0

    # Step 1a: Explore linked issues first
    if ctx.tracker:
        ctx.tracker.step("Exploring linked issues...")

    issue_explorer = IssueExplorerAgent(
        model=ctx.utility_model,
        platform=platform,
        repo=ctx.repo,
        pr_description=ctx.pr_body,
        **base_kwargs,
    )
    issue_prompt = f"Explore linked issues for {ctx.target}"
    issue_cb = ctx.tracker.make_tool_callback() if ctx.tracker else None
    issue_result = await issue_explorer.invoke(issue_prompt, on_tool_call=issue_cb)
    total_cost += issue_result.cost_usd or 0
    ctx.add_usage(issue_result.usage, "IssueExplorer")
    if ctx.tracker:
        ctx.tracker.done("", usage=issue_result.usage)

    issue_context = issue_result.text.strip()
    has_issue_context = issue_context and not _is_empty_result(issue_context)
    if has_issue_context:
        logger.info("Issue context found, enriching analyzer prompt")

    # Step 1b: Run two analyzers in parallel -> structured Review output
    if ctx.tracker:
        ctx.tracker.step("Running reviewers...")

    a0_cb = ctx.tracker.make_tool_callback("Analyzer[0]") if ctx.tracker else None
    a1_cb = ctx.tracker.make_tool_callback("Analyzer[1]") if ctx.tracker else None
    raw_results = await asyncio.gather(
        AnalyzeAgent(
            name="Analyzer[0]",
            model=ctx.review_model,
            platform=platform,
            pr_description=ctx.pr_body,
            diff=ctx.diff_text,
            issue_context=issue_context if has_issue_context else "",
            **base_kwargs,
        ).invoke(base_prompt, on_tool_call=a0_cb),
        AnalyzeAgent(
            name="Analyzer[1]",
            model=ctx.review_model,
            platform=platform,
            pr_description=ctx.pr_body,
            diff=ctx.diff_text,
            issue_context=issue_context if has_issue_context else "",
            **base_kwargs,
        ).invoke(base_prompt, on_tool_call=a1_cb),
        return_exceptions=True,
    )
    # Filter out failed analyzers — one crash shouldn't kill the whole pipeline
    analyzer_results: list[AgentResult] = []
    for r in raw_results:
        if isinstance(r, BaseException):
            logger.warning("Analyzer failed: %s", r)
        else:
            analyzer_results.append(r)
    total_cost += sum(r.cost_usd or 0 for r in analyzer_results)
    for i, r in enumerate(analyzer_results):
        ctx.add_usage(r.usage, f"Analyzer[{i}]")
        if ctx.tracker:
            ctx.tracker.done("", usage=r.usage)

    # Merge comment lists from both analyzers
    all_comments = []
    for r in analyzer_results:
        all_comments.extend(_parse_review_output(r, review_cls, comment_cls))

    if ctx.tracker:
        ctx.tracker.done(f"{len(all_comments)} comments")

    if not all_comments:
        return _empty_result(total_cost)

    # Step 2: Synthesize — merge & deduplicate across reviewers
    if ctx.tracker:
        ctx.tracker.step("Synthesizing...")

    synth_input = _serialize_comments(all_comments)
    if has_issue_context:
        synth_input = f"## Linked issue context\n\n{issue_context}\n\n---\n\n{synth_input}"

    result = await SynthesizerAgent(
        model=ctx.utility_model,
        output_schema=review_cls,
        platform=platform,
        pr_description=ctx.pr_body,
        diff=ctx.diff_text,
        issue_context=issue_context if has_issue_context else "",
        **base_kwargs,
    ).invoke(synth_input)
    total_cost += result.cost_usd or 0
    ctx.add_usage(result.usage, "Synthesizer")
    if ctx.tracker:
        ctx.tracker.done("", usage=result.usage)

    comments = _parse_review_output(result, review_cls, comment_cls)
    if not comments:
        return _empty_result(total_cost)

    # Step 3: Dedup against existing human comments (if any) -> FilterResult
    discussions = ctx.handler.fetch_discussions(ctx.repo, ctx.pr, ctx.sub_env)
    if discussions:
        if ctx.tracker:
            ctx.tracker.step("Deduplicating...")
        result = await DedupAgent(
            model=ctx.utility_model, discussions=discussions, **base_kwargs
        ).invoke(_serialize_numbered(comments))
        total_cost += result.cost_usd or 0
        ctx.add_usage(result.usage, "Dedup")

        comments = _apply_filter(comments, result)
        if ctx.tracker:
            ctx.tracker.done(f"{len(comments)} comments", usage=result.usage)

        if not comments:
            return _empty_result(total_cost)

    # Step 4: Fact-check -> FilterResult
    if ctx.tracker:
        ctx.tracker.step("Fact-checking...")
    fc_cb = ctx.tracker.make_tool_callback() if ctx.tracker else None
    result = await FactCheckAgent(
        model=ctx.review_model,
        pr_description=ctx.pr_body,
        diff=ctx.diff_text,
        issue_context=issue_context if has_issue_context else "",
        **base_kwargs,
    ).invoke(_serialize_numbered(comments), on_tool_call=fc_cb)
    total_cost += result.cost_usd or 0
    ctx.add_usage(result.usage, "FactChecker")

    comments = _apply_filter(comments, result)
    if ctx.tracker:
        ctx.tracker.done(f"{len(comments)} comments", usage=result.usage)

    if not comments:
        return _empty_result(total_cost)

    # Step 5: Style — rewrite bodies only
    if ctx.tracker:
        ctx.tracker.step("Formatting...")
    result = await StyleAgent(
        model=ctx.utility_model,
        platform=platform,
        **base_kwargs,
    ).invoke(_serialize_numbered(comments))
    total_cost += result.cost_usd or 0
    ctx.add_usage(result.usage, "Style")
    if ctx.tracker:
        ctx.tracker.done("", usage=result.usage)

    comments = _apply_style(comments, result)

    review = review_cls(comments=comments)
    return ReviewResult(review=review, cost_usd=total_cost)
