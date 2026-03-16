"""Summary workflow package."""


def __getattr__(name: str):
    if name == "run_summary":
        from code_reviewer.workflows.summary.runner import run_summary

        return run_summary
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["run_summary"]
