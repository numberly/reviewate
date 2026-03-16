"""PostingFixAgent — fixes line numbers for failed inline comments."""

from __future__ import annotations

import re

from pydantic import BaseModel

from code_reviewer.adaptors.repository.github.schema import GitHubReviewComment
from code_reviewer.adaptors.repository.gitlab.schema import GitLabReviewComment
from code_reviewer.agents.base import BaseAgent


class PostingFixAgent(BaseAgent):
    """Lightweight agent that fixes line numbers for failed inline comments.

    When posting fails (e.g., line not in diff), this agent inspects the diff
    and corrects the line number to a valid diff line.
    """

    prompt_file = ""
    permission_mode = "bypassPermissions"
    allowed_tools = ["Bash"]
    max_turns = 3

    async def fix(
        self,
        comment: BaseModel,
        error: str,
        diff_command: str,
    ) -> BaseModel:
        """Attempt to fix a comment's line number based on the diff.

        Args:
            comment: The comment whose line number caused a posting failure.
            error: The error message from the failed post attempt.
            diff_command: Shell command to get the numbered diff.

        Returns:
            A new comment (same type) with the corrected line number.
        """
        if isinstance(comment, GitHubReviewComment):
            file_path = comment.path
            line_num = comment.line
        elif isinstance(comment, GitLabReviewComment):
            file_path = comment.new_path or comment.old_path
            line_num = comment.new_line or comment.old_line
        else:
            return comment

        prompt = (
            f"A review comment failed to post with this error:\n{error}\n\n"
            f"The comment targets file `{file_path}` line {line_num}.\n\n"
            f"Run `{diff_command}` and find the correct NEW line number for this comment. "
            f"The line must appear in the diff on the RIGHT/new side.\n\n"
            f'Return ONLY a JSON object: {{"path": "...", "line": <number>}}'
        )
        result = await self.invoke(prompt)

        match = re.search(r'"line"\s*:\s*(\d+)', result.text)
        if match:
            new_line = int(match.group(1))
            if isinstance(comment, GitHubReviewComment):
                return comment.model_copy(update={"line": new_line})
            elif isinstance(comment, GitLabReviewComment):
                return comment.model_copy(update={"new_line": new_line})
        return comment
