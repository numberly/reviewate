"""Review workflow utility functions."""

from __future__ import annotations

import json
import logging
import re

from pydantic import BaseModel

from code_reviewer.adaptors.repository.schema import Review
from code_reviewer.agents.base import AgentResult
from code_reviewer.guardrail import check_findings as guardrail_check
from code_reviewer.workflows.review.schema import FilterResult, ReviewResult, StyleResult

logger = logging.getLogger(__name__)

_MAX_POST_RETRIES = 1

_MIN_FINDING_LENGTH = 80  # a real finding with File/severity is always longer


def extract_comments(text: str, comment_cls: type[BaseModel]) -> list[BaseModel]:
    """Parse a JSON array of comments from agent output text.

    Handles markdown code blocks (```json ... ```) and raw JSON arrays/objects.
    Uses the provided comment model class for validation.
    """
    raw = None

    # Strategy 1: markdown code block (greedy to handle nested ``` in bodies)
    match = re.search(r"```(?:json)?\s*\n?(.*)\n\s*```", text, re.DOTALL)
    if match:
        try:
            raw = json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Strategy 2: bare JSON array (try before object to avoid matching inner objects)
    if raw is None:
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                raw = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass

    # Strategy 3: outermost JSON object via brace matching
    if raw is None:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                raw = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass

    if raw is None:
        logger.warning("No valid JSON found in agent output")
        return []

    # Handle both {"comments": [...]} wrapper and bare [...] array
    if isinstance(raw, dict) and "comments" in raw:
        raw = raw["comments"]

    if not isinstance(raw, list):
        logger.warning("Expected JSON array, got %s", type(raw).__name__)
        return []

    comments = []
    for item in raw:
        try:
            comments.append(comment_cls.model_validate(item))
        except Exception as e:
            logger.warning("Skipping invalid comment: %s", e)
    return comments


def _serialize_comments(comments: list[BaseModel]) -> str:
    """JSON dump {"comments": [...]} for review agents."""
    return json.dumps({"comments": [c.model_dump() for c in comments]})


def _serialize_numbered(comments: list[BaseModel]) -> str:
    """JSON dump [{index: 0, ...}, ...] for filter agents."""
    items = []
    for i, c in enumerate(comments):
        d = c.model_dump()
        d["index"] = i
        items.append(d)
    return json.dumps(items)


def _parse_review_output(
    result: AgentResult,
    review_cls: type[Review],
    comment_cls: type[BaseModel],
) -> list[BaseModel]:
    """Parse Review from structured_output, fallback to extract_comments."""
    comments: list[BaseModel] = []
    if result.structured_output:
        try:
            review = review_cls.model_validate(result.structured_output)
            comments = list(review.comments)
            logger.info("Parsed %d comments from structured output", len(comments))
        except Exception as e:
            logger.warning("Structured output validation failed: %s", e)
    if not comments:
        comments = extract_comments(result.text, comment_cls)
    return comments


def _apply_filter(comments: list[BaseModel], result: AgentResult) -> list[BaseModel]:
    """Parse FilterResult from structured_output, apply keep_indices. Fallback: keep all."""
    if result.structured_output:
        try:
            fr = FilterResult.model_validate(result.structured_output)
            valid = [i for i in fr.keep_indices if 0 <= i < len(comments)]
            filtered = [comments[i] for i in valid]
            logger.info("Filter kept %d/%d comments", len(filtered), len(comments))
            return filtered
        except Exception as e:
            logger.warning("FilterResult validation failed, keeping all: %s", e)
    # Fallback: try to parse from text
    try:
        text = result.text.strip()
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            raw = json.loads(match.group())
            fr = FilterResult.model_validate(raw)
            valid = [i for i in fr.keep_indices if 0 <= i < len(comments)]
            filtered = [comments[i] for i in valid]
            logger.info("Filter kept %d/%d comments (text fallback)", len(filtered), len(comments))
            return filtered
    except Exception as e:
        logger.warning("FilterResult text fallback failed, keeping all: %s", e)
    return comments


def _apply_style(comments: list[BaseModel], result: AgentResult) -> list[BaseModel]:
    """Apply StyleResult bodies to existing comments. Fallback: keep originals."""
    if result.structured_output:
        try:
            sr = StyleResult.model_validate(result.structured_output)
            if len(sr.bodies) == len(comments):
                styled = []
                for comment, body in zip(comments, sr.bodies, strict=True):
                    d = comment.model_dump()
                    d["body"] = body
                    styled.append(type(comment).model_validate(d))
                logger.info("Applied %d styled bodies", len(styled))
                return styled
            logger.warning(
                "StyleResult count mismatch (%d vs %d), keeping originals",
                len(sr.bodies),
                len(comments),
            )
        except Exception as e:
            logger.warning("StyleResult validation failed, keeping originals: %s", e)
    return comments


def _is_empty_result(text: str) -> bool:
    """Check if agent output is too short to contain a real finding."""
    return len(text.strip()) < _MIN_FINDING_LENGTH


def _empty_result(cost: float) -> ReviewResult:
    """Return an empty ReviewResult."""
    return ReviewResult(review=Review(comments=[]), cost_usd=cost)


def _apply_guardrail(review: Review, comments: list) -> tuple[Review, list]:
    """Scan comments for leaked secrets. Returns filtered review + comments."""
    result = guardrail_check(comments)
    if result.safe:
        return review, comments

    logger.warning(
        "Guardrail flagged %d comments: %s",
        len(result.flagged_indices),
        result.reasons,
    )
    flagged = set(result.flagged_indices)
    filtered = [c for i, c in enumerate(comments) if i not in flagged]
    logger.info("%d comments remain after guardrail", len(filtered))
    return type(review)(comments=filtered), filtered


async def _post_with_retry(ctx, review: Review) -> int:
    """Post review comments with retry loop for line number fixes.

    Returns the number of successfully posted comments.
    """
    from code_reviewer.agents.post_fixer import PostingFixAgent

    handler = ctx.handler
    result = handler.post_review(review, ctx.repo, ctx.pr, ctx.sub_env)
    posted = result.posted

    diff_command = handler.get_diff_command(ctx.repo, ctx.pr)

    for attempt in range(1, _MAX_POST_RETRIES + 1):
        if not result.failed:
            break

        logger.info(
            "Posting retry %d/%d: %d comments failed",
            attempt,
            _MAX_POST_RETRIES,
            len(result.failed),
        )

        fixer = PostingFixAgent(cwd=ctx.workspace, env=ctx.agent_env)
        fixer.model = ctx.utility_model
        fixed_comments = []
        for failure in result.failed:
            try:
                fixed = await fixer.fix(failure.comment, failure.error, diff_command)
                fixed_comments.append(fixed)
            except Exception as e:
                logger.warning("PostingFixAgent failed: %s", e)
                fixed_comments.append(failure.comment)

        retry_review = type(review)(comments=fixed_comments)
        result = handler.post_review(retry_review, ctx.repo, ctx.pr, ctx.sub_env)
        posted += result.posted

    # Fall back remaining failures to regular comments
    if result.failed:
        logger.info(
            "%d comments failed inline after %d retries, falling back to regular comments",
            len(result.failed),
            _MAX_POST_RETRIES,
        )
        for failure in result.failed:
            if handler.post_regular_comment(failure.comment, ctx.repo, ctx.pr, ctx.sub_env):
                posted += 1

    return posted
