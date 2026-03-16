#!/usr/bin/env python3
"""PreToolUse hook that enforces a tool call budget per agent session.

Reads REVIEWATE_TOOL_BUDGET from env (default: unlimited).
Tracks calls in /tmp/reviewate_budget_{session_id}.
Denies the call when the budget is exceeded.
"""

import json
import os
import sys


def main() -> None:
    data = json.load(sys.stdin)
    tool_name = data.get("tool_name", "")
    session_id = data.get("session_id", "unknown")

    # Only count exploration tools — skip StructuredOutput, ToolSearch, etc.
    if tool_name not in ("Read", "Grep", "Glob", "Bash"):
        sys.exit(0)

    budget = int(os.environ.get("REVIEWATE_TOOL_BUDGET", "9999"))
    counter_file = f"/tmp/reviewate_budget_{session_id}"

    try:
        count = int(open(counter_file).read().strip())  # noqa: SIM115
    except (FileNotFoundError, ValueError):
        count = 0

    count += 1

    with open(counter_file, "w") as f:
        f.write(str(count))

    if count > budget:
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"TOOL BUDGET EXHAUSTED ({count}/{budget}). "
                        "You have used all your tool calls. "
                        "Do NOT invoke any more tools. "
                        "Output your findings IMMEDIATELY with the information "
                        "you have gathered so far."
                    ),
                }
            },
            sys.stdout,
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
