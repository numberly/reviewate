"""Application options schema.

This module defines optional configuration that can be accessed via app.options.
All fields are nullable - they are optional settings that may or may not be configured.
"""

from pydantic import BaseModel, Field


class CodeReviewerOptions(BaseModel):
    """Options for the code reviewer container.

    These are passed as environment variables to the review container.
    """

    oauth_token: str | None = Field(
        default=None,
        description="Claude Code OAuth token (from `claude setup-token`, for subscription users)",
    )
    anthropic_api_key: str | None = Field(
        default=None,
        description="Anthropic API key for Claude models",
    )
    anthropic_base_url: str | None = Field(
        default=None,
        description="Custom base URL for Anthropic API (for LiteLLM proxy)",
    )
    review_model: str | None = Field(
        default=None,
        description="Model for review tier — AnalyzeAgent, FactCheckAgent (e.g., sonnet, opus)",
    )
    utility_model: str | None = Field(
        default=None,
        description="Model for utility tier — SynthesizerAgent, DedupAgent, StyleAgent, etc. (e.g., haiku)",
    )


class FeedbackLoopOptions(BaseModel):
    """Options for the feedback loop feature.

    When enabled, Reviewate learns from user feedback (thumbs-down, reply comments,
    dismissed reviews) to improve future code reviews.
    """

    enabled: bool = Field(
        default=False,
        description="Enable/disable feedback loop feature",
    )
    model: str | None = Field(
        default=None,
        description="Model name for summarization (e.g., gemini-2.0-flash)",
    )
    provider: str | None = Field(
        default=None,
        description="LLM provider (gemini, anthropic, openai, openrouter)",
    )
    api_key: str | None = Field(
        default=None,
        description="API key for the LLM provider (optional if set via env vars)",
    )


class Options(BaseModel):
    """Root options container.

    Access via app.options.code_reviewer.anthropic_api_key, etc.
    """

    code_reviewer: CodeReviewerOptions = Field(default_factory=CodeReviewerOptions)
    feedback_loop: FeedbackLoopOptions = Field(default_factory=FeedbackLoopOptions)
    expose_error_details: bool = Field(
        default=True,
        description="Expose technical error details in API responses (set false for cloud)",
    )
