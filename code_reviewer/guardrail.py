"""Guardrail — scans finding bodies for leaked secrets before posting.

Uses gitleaks (https://github.com/gitleaks/gitleaks) via stdin to detect
secrets in finding bodies. Falls back to safe (no findings blocked) if
gitleaks is not installed.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from typing import Any

from code_reviewer.workflows.schema import GuardrailResult

logger = logging.getLogger(__name__)


def check_findings(comments: list[Any]) -> GuardrailResult:
    """Scan finding bodies for secrets using gitleaks.

    Pipes each finding body through `gitleaks stdin` and flags any that
    contain detected secrets.

    Falls back to safe (nothing blocked) if gitleaks is not installed.
    """
    if not comments:
        return GuardrailResult(safe=True)

    if not shutil.which("gitleaks"):
        logger.debug("gitleaks not installed, skipping guardrail")
        return GuardrailResult(safe=True)

    flagged_indices: list[int] = []
    reasons: list[str] = []

    for i, comment in enumerate(comments):
        leaks = _scan_string(comment.body)
        if leaks:
            flagged_indices.append(i)
            descriptions = ", ".join(leak.get("Description", "secret") for leak in leaks)
            reasons.append(f"Comment {i}: {descriptions}")

    return GuardrailResult(
        safe=len(flagged_indices) == 0,
        flagged_indices=flagged_indices,
        reasons=reasons,
    )


def _scan_string(text: str) -> list[dict]:
    """Run gitleaks stdin on a string. Returns list of findings (empty = clean)."""
    try:
        proc = subprocess.run(
            ["gitleaks", "stdin", "--no-banner", "--report-format", "json", "--report-path", "-"],
            input=text,
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Exit code 0 = no leaks, 1 = leaks found, other = error
        if proc.returncode == 1 and proc.stdout.strip():
            return json.loads(proc.stdout)
        return []
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
        logger.debug("gitleaks scan failed: %s", e)
        return []
