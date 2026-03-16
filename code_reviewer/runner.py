"""Runner — validates config, builds context, and dispatches workflows.

Heavy imports live here — this module is only imported after argument
parsing (and --help) has completed.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
import tempfile
import time

from code_reviewer.adaptors.diff_filter import filter_diff
from code_reviewer.adaptors.repository import get_handler
from code_reviewer.config import Config
from code_reviewer.errors import ErrorType, error_type_for_exception
from code_reviewer.logging_config import setup_logging
from code_reviewer.output import ProgressTracker, emit_error, emit_result, print_error
from code_reviewer.workflows import RunContext, run_review, run_summary

logger = logging.getLogger(__name__)


def _format_usage(usage: dict[str, int] | None) -> str:
    """Format usage dict into a compact readable string."""
    if not usage:
        return "n/a"
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


def _build_context(args: argparse.Namespace) -> RunContext:
    """Build the RunContext from CLI args and environment."""
    config = Config.from_env()
    config.validate_auth()
    logger.info(
        "Config loaded (api_key=%s, oauth=%s)",
        "set" if config.api_key else "unset",
        "set" if config.oauth_token else "unset",
    )

    agent_env = config.build_agent_env()
    sub_env = os.environ.copy()
    sub_env.update(agent_env)

    team_guidelines = os.getenv("TEAM_GUIDELINES")
    system_extra = ""
    if team_guidelines:
        system_extra = f"\n\n<team_guidelines>\n{team_guidelines}\n</team_guidelines>"

    review_model = config.review_model or "sonnet"
    utility_model = config.utility_model or "haiku"

    return RunContext(
        handler=get_handler(args.platform),
        repo=args.repo,
        pr=args.pr,
        workspace=tempfile.mkdtemp(prefix="reviewate-"),
        agent_env=agent_env,
        sub_env=sub_env,
        system_extra=system_extra,
        review_model=review_model,
        utility_model=utility_model,
        dry_run=args.dry_run,
        debug=args.debug,
    )


async def run(args: argparse.Namespace) -> int:
    """Run the review/summary workflows."""
    start_time = time.time()

    is_tty = sys.stderr.isatty()
    log_level = os.getenv("LOG_LEVEL", "CRITICAL" if is_tty else "INFO")
    setup_logging(log_level, debug=args.debug)

    try:
        ctx = _build_context(args)
    except Exception as e:
        msg = f"{e}"
        emit_error(
            error_type_for_exception(e),
            f"{msg} (after {time.time() - start_time:.1f}s)",
            is_tty=is_tty,
        )
        if is_tty:
            print_error(msg)
        return 1

    # TTY progress tracker
    if is_tty and not args.debug:
        workflows_label = " + ".join(
            f for f, enabled in [("review", args.review), ("summary", args.summary)] if enabled
        )
        ctx.tracker = ProgressTracker(
            repo=ctx.repo, pr=ctx.pr, workflows=workflows_label, model=ctx.review_model
        )
        ctx.tracker.start()

    repo_dir = os.path.join(ctx.workspace, ctx.repo.split("/")[-1])
    logger.info("Workspace: %s", ctx.workspace)
    logger.info("Target: %s", ctx.target)

    exit_error: str | None = None
    try:
        # Validate & clone
        if ctx.tracker:
            ctx.tracker.step("Validating...")
        ctx.handler.validate_pr(ctx.repo, ctx.pr, ctx.sub_env)
        logger.info("PR/MR validated")

        if ctx.tracker:
            ctx.tracker.step("Downloading source...")
        ctx.handler.download_source(ctx.repo, ctx.pr, repo_dir, ctx.sub_env)
        logger.info("Source downloaded to %s", repo_dir)

        # Pre-fetch PR body + diff for cache-friendly agent prompts
        ctx.pr_body = ctx.handler.fetch_pr_body(ctx.repo, ctx.pr, ctx.sub_env)
        raw_diff = ctx.handler.fetch_diff(ctx.repo, ctx.pr, ctx.sub_env)
        ctx.diff_text = filter_diff(raw_diff)
        logger.info(
            "Pre-fetched PR body (%d chars) and diff (%d chars, %d raw)",
            len(ctx.pr_body),
            len(ctx.diff_text),
            len(raw_diff),
        )

        # Run workflows
        if args.summary:
            await run_summary(ctx)
        if args.review:
            await run_review(ctx)

    except KeyboardInterrupt:
        exit_error = "User cancelled"
        emit_error(ErrorType.INTERRUPTED, "User cancelled the operation", is_tty=is_tty)
        return 1
    except Exception as e:
        exit_error = str(e)
        if args.debug:
            import traceback

            traceback.print_exc()
        emit_error(error_type_for_exception(e), str(e), is_tty=is_tty)
        return 1
    finally:
        if ctx.tracker is not None:
            if exit_error:
                ctx.tracker.fail(exit_error)
            else:
                ctx.tracker.finish(cost_usd=ctx.total_cost or None, usage=ctx.total_usage)
                if ctx.summary_body:
                    ctx.tracker.print_summary_panel(ctx.summary_body)
                if ctx.review_comments:
                    ctx.tracker.print_review_panels(ctx.review_comments)
                elif args.review:
                    ctx.tracker.print_lgtm()
        shutil.rmtree(ctx.workspace, ignore_errors=True)

    if ctx.total_cost:
        ctx.result_data["cost_usd"] = ctx.total_cost
    if ctx.total_usage:
        ctx.result_data["usage"] = ctx.total_usage
    elapsed = time.time() - start_time

    # Per-agent usage breakdown
    for agent_name, agent_usage in ctx.agent_usages:
        logger.info("  %s: %s", agent_name, _format_usage(agent_usage))

    logger.info(
        "Total: %.1fs, cost %s, %s",
        elapsed,
        f"${ctx.total_cost:.4f}" if ctx.total_cost else "n/a",
        _format_usage(ctx.total_usage),
    )
    emit_result(ctx.result_data, is_tty=is_tty)
    return 0
