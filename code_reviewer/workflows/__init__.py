"""Workflow modules for review and summary pipelines."""

from code_reviewer.workflows.context import RunContext


def __getattr__(name: str):
    if name == "run_review":
        from code_reviewer.workflows.review import run_review

        return run_review
    if name == "run_summary":
        from code_reviewer.workflows.summary.runner import run_summary

        return run_summary
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["RunContext", "run_review", "run_summary"]
