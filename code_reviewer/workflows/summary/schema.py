"""Summary workflow schema types."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SummaryOutput(BaseModel):
    """Output from summarizer agent — raw bullet-point description."""

    model_config = ConfigDict(extra="forbid")

    description: str


class ParsedSummaryOutput(BaseModel):
    """Output from summary parser agent — refined/condensed description."""

    model_config = ConfigDict(extra="forbid")

    description: str
