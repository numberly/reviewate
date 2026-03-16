"""Reviewate — AI-powered code review for GitHub and GitLab.

Uses Claude Agent SDK for multi-agent code review with Claude Code's
built-in tools (Read, Grep, Glob, Bash) and gh/glab CLI for platform interaction.
"""

from importlib.metadata import PackageNotFoundError as _PNF
from importlib.metadata import version as _version

try:
    __version__ = _version("reviewate")
except _PNF:
    __version__ = "0.0.0-dev"
