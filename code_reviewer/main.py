#!/usr/bin/env python3
"""CLI entry point for Reviewate

Usage:
    reviewate owner/repo -p 123                    # review (default)
    reviewate summary owner/repo -p 123            # summary only
    reviewate full owner/repo -p 123               # review + summary
    reviewate review owner/repo -p 123 --dry-run   # explicit review

    # From URL (platform, repo, PR auto-detected):
    reviewate https://github.com/org/repo/pull/48
    reviewate https://gitlab.com/group/repo/-/merge_requests/1
"""

from __future__ import annotations

import asyncio
import os
import sys

# Fix imports when running as script (not as module)
if __name__ == "__main__" and __package__ is None:
    _parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, _parent)
    __package__ = "code_reviewer"

from code_reviewer.cli import parse_args


def cli_entry() -> None:
    """Sync entry point for `pip install reviewate` console script."""
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as e:
        from rich.console import Console

        _console = Console(stderr=True, highlight=False)
        _console.print(f"[bold red]Error:[/] {e}")
        if "--debug" in sys.argv:
            _console.print_exception()
        sys.exit(1)


async def main() -> int:
    """Parse args, then hand off to the runner for heavy work."""
    args = parse_args()

    # Handle config subcommand (no review, just re-run setup)
    if args.command == "config":
        from rich.console import Console

        from code_reviewer.config_file import _run_interactive_setup

        try:
            _run_interactive_setup()
        except KeyboardInterrupt:
            Console(stderr=True, highlight=False).print("\n[dim]Cancelled.[/]")
            return 1
        return 0

    # Heavy imports only happen here — after --help has already exited
    from code_reviewer.runner import run

    return await run(args)


if __name__ == "__main__":
    cli_entry()
