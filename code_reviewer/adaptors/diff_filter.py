"""Filter noise files from diffs before passing to agents.

Lock files, generated files, and vendored dependencies bloat diffs
with zero review value and can exceed OS ARG_MAX limits when embedded
in system prompts.
"""

from __future__ import annotations

import re

# Patterns matched against file paths in diff headers.
# Uses fnmatch-style globs converted to regex.
EXCLUDED_PATTERNS: list[str] = [
    # Python
    "uv.lock",
    "poetry.lock",
    "Pipfile.lock",
    "requirements*.txt",
    # JavaScript / TypeScript
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lockb",
    "bun.lock",
    # Ruby
    "Gemfile.lock",
    # PHP
    "composer.lock",
    # Rust
    "Cargo.lock",
    # Go
    "go.sum",
    # .NET
    "packages.lock.json",
    # Dart / Flutter
    "pubspec.lock",
    # Elixir
    "mix.lock",
    # Swift
    "Package.resolved",
    # Vendored / generated
    "vendor/*",
    "node_modules/*",
    ".yarn/*",
    # IDE / editor
    ".idea/*",
    ".vscode/*",
    # Build artifacts
    "dist/*",
    "build/*",
    "__pycache__/*",
    # Auto-generated
    "*.min.js",
    "*.min.css",
    "*.map",
    "*.generated.*",
    "*.pb.go",
    "*.g.dart",
    # Migrations (large, auto-generated)
    "*.snapshot",
]

# Compile patterns to a single regex for performance
_PATTERN_RE = re.compile(
    "|".join(p.replace(".", r"\.").replace("*", ".*").replace("?", ".") for p in EXCLUDED_PATTERNS)
)

# Matches diff file headers from `git diff` and `diffn` output.
# Handles both "diff --git a/path b/path" and "--- a/path" / "+++ b/path"
_DIFF_HEADER_RE = re.compile(r"^diff --git a/(.*?) b/", re.MULTILINE)


def filter_diff(diff: str) -> str:
    """Remove excluded file sections from a unified diff.

    Splits on `diff --git` boundaries and drops sections
    whose file path matches any excluded pattern.
    """
    if not diff:
        return diff

    # Split into per-file sections
    sections = re.split(r"(?=^diff --git )", diff, flags=re.MULTILINE)

    kept: list[str] = []
    dropped: list[str] = []

    for section in sections:
        header = _DIFF_HEADER_RE.match(section)
        if header:
            path = header.group(1)
            if _is_excluded(path):
                dropped.append(path)
                continue
        kept.append(section)

    if dropped:
        import logging

        logger = logging.getLogger(__name__)
        logger.info("Filtered %d noise file(s) from diff: %s", len(dropped), ", ".join(dropped))

    return "".join(kept)


def _is_excluded(path: str) -> bool:
    """Check if a file path matches any excluded pattern."""
    # Match against the full path and the basename
    return bool(_PATTERN_RE.fullmatch(path) or _PATTERN_RE.fullmatch(path.split("/")[-1]))
