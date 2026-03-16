"""Shared schema types for workflows."""

from __future__ import annotations

from pydantic import BaseModel


class GuardrailResult(BaseModel):
    """Result from the guardrail secret scan."""

    safe: bool
    flagged_indices: list[int] = []
    reasons: list[str] = []
