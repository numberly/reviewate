"""diffn — pipe-friendly wrapper that adds old/new line numbers to git diffs.

Usage:
    gh pr diff 123 | diffn
    glab mr diff 491 | diffn
    git diff HEAD~1 | diffn

Output format:
    Added lines:    "      42   :+code"
    Deleted lines:  "41        :-code"
    Context lines:  "41   , 42   : code"
"""

from __future__ import annotations

import re
import sys

HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def format_diff_with_line_numbers(diff_text: str) -> str:
    """Add old/new line numbers to each line of a unified diff."""
    output_lines: list[str] = []
    old_line = 0
    new_line = 0
    in_hunk = False

    for line in diff_text.splitlines():
        match = HUNK_HEADER.match(line)
        if match:
            old_line = int(match.group(1))
            new_line = int(match.group(2))
            in_hunk = True
            output_lines.append(line)
            continue

        # Outside a hunk — file headers, index lines, etc.
        if not in_hunk or not line:
            output_lines.append(line)
            continue

        prefix = line[0]
        content = line[1:]

        if prefix == "+":
            output_lines.append(f"      {new_line:<5}:+{content}")
            new_line += 1
        elif prefix == "-":
            output_lines.append(f"{old_line:<5}     :-{content}")
            old_line += 1
        elif prefix == " ":
            output_lines.append(f"{old_line:<5}, {new_line:<5}: {content}")
            old_line += 1
            new_line += 1
        else:
            # Non-hunk line (e.g. "\ No newline at end of file") — reset
            in_hunk = False
            output_lines.append(line)

    return "\n".join(output_lines)


def main() -> None:
    """Read diff from stdin and print with line numbers."""
    diff_text = sys.stdin.read()
    if diff_text:
        print(format_diff_with_line_numbers(diff_text))


if __name__ == "__main__":
    main()
