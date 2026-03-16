"""Batch job to summarize feedback into team guidelines.

This job runs periodically (e.g., weekly) to process raw feedback
and generate natural language team guidelines using an LLM.

Also provides lazy regeneration: guidelines are refreshed on-demand
before a review starts if they're stale and new feedback exists.
"""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

import litellm

from api.context import get_current_app
from api.database import (
    db_get_all_unprocessed_feedback_for_org,
    db_get_effective_team_guidelines,
    db_mark_feedback_processed,
    db_upsert_team_guidelines,
)
from api.database.organization import db_get_all_organizations
from api.models import Feedback

logger = logging.getLogger(__name__)

# Guidelines are considered stale after this many days
GUIDELINES_STALE_DAYS = 7

# Prompt template for summarizing feedback into guidelines
SUMMARIZATION_PROMPT = """You are analyzing feedback from a development team about AI code review comments.

Here is the feedback collected from the team:
{feedback_list}

Based on this feedback, write concise team preferences for the code reviewer.
Format as a short bulleted list of DO and DON'T guidelines.
Only include patterns with clear consensus (multiple similar feedbacks).
Keep it under 10 guidelines total.

Focus on:
1. What types of issues the team doesn't want flagged (false positives)
2. What patterns the team prefers or requires
3. Domain-specific preferences (e.g., Python, JavaScript, testing)

Example output:
- Don't flag missing type hints in test files
- Don't suggest docstrings for private methods
- Do suggest early return patterns to reduce nesting
- Do flag print statements (use logging instead)
- Don't flag unused variables prefixed with underscore

If the feedback is inconsistent or unclear, only include the most obvious patterns.
If there's not enough feedback to establish clear patterns, respond with: "Not enough feedback to establish team preferences yet."

Team preferences:"""


def _build_feedback_prompt(feedbacks: list[Feedback]) -> str:
    """Build the prompt with feedback list.

    Args:
        feedbacks: List of feedback records

    Returns:
        Complete prompt with feedback inserted
    """
    feedback_items = []
    for fb in feedbacks:
        item = f"- Type: {fb.feedback_type}"
        if fb.review_comment:
            # Truncate long comments
            comment = (
                fb.review_comment[:500] + "..."
                if len(fb.review_comment) > 500
                else fb.review_comment
            )
            item += f'\n  AI Comment: "{comment}"'
        if fb.user_response:
            response = (
                fb.user_response[:300] + "..." if len(fb.user_response) > 300 else fb.user_response
            )
            item += f'\n  User Reply: "{response}"'
        if fb.file_path:
            item += f"\n  File: {fb.file_path}"
        feedback_items.append(item)

    feedback_list = "\n".join(feedback_items)
    return SUMMARIZATION_PROMPT.format(feedback_list=feedback_list)


def _build_litellm_model(provider: str | None, model: str | None) -> str:
    """Build LiteLLM model string from provider and model.

    Args:
        provider: Provider name (gemini, anthropic, openai, openrouter)
        model: Model name

    Returns:
        LiteLLM format model string (e.g., "gemini/gemini-2.0-flash")
    """
    # Default to gemini if not specified
    provider = provider or "gemini"
    model = model or "gemini-2.0-flash"

    # Build LiteLLM format: provider/model
    return f"{provider}/{model}"


async def summarize_feedback_for_org(
    organization_id: UUID,
    model: str | None = None,
    provider: str | None = None,
    api_key: str | None = None,
) -> tuple[bool, str]:
    """Summarize unprocessed feedback for an organization into guidelines.

    Manages its own short-lived DB sessions to avoid holding connections
    during the LLM call.

    Args:
        organization_id: Organization ID
        model: Optional model name override
        provider: Optional provider override
        api_key: Optional API key override

    Returns:
        Tuple of (success, message)
    """
    app = get_current_app()

    # Get configuration
    options = app.options.feedback_loop
    if not options.enabled:
        return False, "Feedback loop is disabled"

    # Build LiteLLM model string
    llm_model = _build_litellm_model(
        provider=provider or options.provider,
        model=model or options.model,
    )
    llm_api_key = api_key or options.api_key

    # Phase 1 (session): Get unprocessed feedback
    with app.database.session() as db:
        feedbacks = db_get_all_unprocessed_feedback_for_org(db, organization_id)
    if not feedbacks:
        logger.info(f"No unprocessed feedback for org {organization_id}")
        return True, "No unprocessed feedback"

    logger.info(f"Processing {len(feedbacks)} feedback records for org {organization_id}")

    try:
        # Phase 2 (no session): LLM call
        prompt = _build_feedback_prompt(feedbacks)

        response = await litellm.acompletion(
            model=llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1024,
            api_key=llm_api_key,
        )

        guidelines_text = response.choices[0].message.content
        if not guidelines_text:
            return False, "Empty response from LLM"

        # Phase 3 (session): DB writes
        feedback_ids = [fb.id for fb in feedbacks]

        if "not enough feedback" in guidelines_text.lower():
            logger.info(f"Not enough feedback to establish patterns for org {organization_id}")
            with app.database.session() as db:
                db_mark_feedback_processed(db, feedback_ids)
            return True, "Not enough feedback to establish patterns"

        with app.database.session() as db:
            db_upsert_team_guidelines(
                db=db,
                organization_id=organization_id,
                guidelines_text=guidelines_text.strip(),
                feedback_count=len(feedbacks),
                repository_id=None,  # Org-wide guidelines
            )
            db_mark_feedback_processed(db, feedback_ids)

        logger.info(
            f"Successfully summarized {len(feedbacks)} feedbacks into guidelines for org {organization_id}"
        )
        return True, f"Processed {len(feedbacks)} feedbacks"

    except Exception as e:
        logger.error(f"Failed to summarize feedback for org {organization_id}: {e}", exc_info=True)
        return False, str(e)


async def summarize_all_feedback(
    model: str | None = None,
    provider: str | None = None,
    api_key: str | None = None,
) -> dict[str, tuple[bool, str]]:
    """Summarize feedback for all organizations.

    This is the main entry point for the periodic batch job.

    Args:
        model: Optional model name override
        provider: Optional provider override
        api_key: Optional API key override

    Returns:
        Dict mapping org_id to (success, message) tuples
    """
    app = get_current_app()
    options = app.options.feedback_loop

    if not options.enabled:
        logger.info("Feedback loop is disabled, skipping batch summarization")
        return {}

    # Get all organizations (short-lived session)
    with app.database.session() as db:
        organizations = db_get_all_organizations(db)

    logger.info(f"Processing feedback for {len(organizations)} organizations")

    results: dict[str, tuple[bool, str]] = {}
    for org in organizations:
        org_id = str(org.id)
        try:
            success, message = await summarize_feedback_for_org(
                organization_id=org.id,
                model=model,
                provider=provider,
                api_key=api_key,
            )
            results[org_id] = (success, message)
        except Exception as e:
            logger.error(f"Failed to process org {org_id}: {e}", exc_info=True)
            results[org_id] = (False, str(e))

    return results


def _is_guidelines_stale(guidelines) -> bool:
    """Check if guidelines are stale and should be refreshed.

    Args:
        guidelines: TeamGuidelines object or None

    Returns:
        True if guidelines don't exist or are older than GUIDELINES_STALE_DAYS
    """
    if guidelines is None:
        return True

    stale_threshold = datetime.now(UTC) - timedelta(days=GUIDELINES_STALE_DAYS)
    return guidelines.last_updated < stale_threshold


async def get_or_refresh_team_guidelines(
    organization_id: UUID,
    repository_id: UUID | None = None,
) -> str | None:
    """Get team guidelines, refreshing them if stale and new feedback exists.

    This is the lazy regeneration entry point called before starting a review.
    If feedback loop is disabled, returns existing guidelines without refresh.

    Manages its own short-lived DB sessions to avoid holding connections
    during the LLM call in summarize_feedback_for_org.

    Args:
        organization_id: Organization ID
        repository_id: Optional repository ID for repo-specific guidelines

    Returns:
        Guidelines text if available, None otherwise
    """
    app = get_current_app()
    options = app.options.feedback_loop

    # Phase 1 (session): Check staleness
    with app.database.session() as db:
        guidelines = db_get_effective_team_guidelines(db, organization_id, repository_id)

        if not options.enabled:
            return guidelines.guidelines_text if guidelines else None

        stale = _is_guidelines_stale(guidelines)
        unprocessed = db_get_all_unprocessed_feedback_for_org(db, organization_id) if stale else []

    if not stale or not unprocessed:
        return guidelines.guidelines_text if guidelines else None

    # Phase 2 (no session held here): LLM call + DB writes inside summarize_feedback_for_org
    logger.info(
        f"Guidelines stale with {len(unprocessed)} unprocessed feedbacks, regenerating for org {organization_id}"
    )
    success, message = await summarize_feedback_for_org(organization_id)
    if success:
        # Phase 3 (session): Refresh guidelines after regeneration
        with app.database.session() as db:
            guidelines = db_get_effective_team_guidelines(db, organization_id, repository_id)
    else:
        logger.warning(f"Failed to regenerate guidelines: {message}")

    return guidelines.guidelines_text if guidelines else None
