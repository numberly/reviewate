"""Review workflow package."""


def __getattr__(name: str):
    if name == "run_review":
        from code_reviewer.workflows.review.runner import run_review

        return run_review
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["run_review"]
