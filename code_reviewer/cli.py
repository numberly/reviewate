"""Argument parsing and URL resolution for the Reviewate CLI.

Pure functions, no async — used by main.py to build an argparse.Namespace.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

KNOWN_SUBCOMMANDS = {"review", "summary", "full", "config"}


def _preprocess_argv(argv: list[str] | None = None) -> list[str]:
    """Insert 'review' subcommand if the first arg isn't a known subcommand."""
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        return ["--help"]
    if argv[0] in ("-h", "--help", "--version"):
        return argv
    if argv[0] == "version":
        return ["--version"]
    if argv[0] not in KNOWN_SUBCOMMANDS:
        return ["review"] + argv
    return argv


def _parse_pr_url(url: str) -> tuple[str, str, str, str | None]:
    """Parse a PR/MR URL into (platform, repo, pr_number, api_url_or_none).

    Supported formats:
      - GitHub:  https://github.com/owner/repo/pull/123
      - GitLab:  https://gitlab.com/group/project/-/merge_requests/123
      - GitLab (self-hosted): https://gitlab.example.com/group/project/-/merge_requests/123
      - GitLab (subgroups):   https://gitlab.example.com/g/sub/project/-/merge_requests/123
    """
    gh_match = re.match(r"https?://github\.com/([^/]+/[^/]+)/pull/(\d+)(?:/\w+)?/?$", url)
    if gh_match:
        repo, pr = gh_match.group(1), gh_match.group(2)
        return "github", repo, pr, None

    gl_match = re.match(r"https?://([^/]+)/(.+?)/-/merge_requests/(\d+)/?$", url)
    if gl_match:
        host, repo_path, pr = gl_match.group(1), gl_match.group(2), gl_match.group(3)
        if "/" not in repo_path:
            raise argparse.ArgumentTypeError(
                f"Invalid GitLab URL: repo path '{repo_path}' must contain at least owner/project"
            )
        api_url = None if host == "gitlab.com" else f"https://{host}/api/v4"
        return "gitlab", repo_path, pr, api_url

    raise argparse.ArgumentTypeError(
        f"Unrecognized PR/MR URL: {url}\n"
        "Expected formats:\n"
        "  GitHub:  https://github.com/owner/repo/pull/123\n"
        "  GitLab:  https://gitlab.com/group/project/-/merge_requests/123"
    )


def _make_common_parser() -> argparse.ArgumentParser:
    """Create a parent parser with shared flags."""
    common = argparse.ArgumentParser(add_help=False)

    common.add_argument(
        "-p",
        "--pr",
        required=False,
        default=None,
        help="Pull request / merge request number (auto-detected from URL)",
    )

    common.add_argument(
        "--platform",
        default="github",
        choices=["github", "gitlab"],
        help="Git platform (default: github)",
    )

    common.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without posting to platform",
    )

    common.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    common.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    return common


def _add_repo_arg(parser: argparse.ArgumentParser) -> None:
    """Add the positional repo argument to a subparser."""
    parser.add_argument(
        "repo",
        help="Repository 'owner/repo' or full PR/MR URL",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments"""
    from code_reviewer import __version__

    common_parser = _make_common_parser()

    parser = argparse.ArgumentParser(
        prog="reviewate",
        description="Reviewate - AI-powered code review for GitHub and GitLab",
        parents=[common_parser],
        epilog=(
            "examples:\n"
            "  reviewate owner/repo -p 123                          review (default)\n"
            "  reviewate https://github.com/org/repo/pull/48        review from URL\n"
            "  reviewate summary owner/repo -p 123                  summary only\n"
            "  reviewate full owner/repo -p 123                     review + summary\n"
            "  reviewate review owner/repo -p 123 --dry-run         review without posting\n"
            "  reviewate config                                     re-run setup wizard\n"
            "\n"
            "docs: https://reviewate.com/docs"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", title="commands", metavar="<command>")

    for name, help_text in [
        ("review", "Run code review (default when no command specified)"),
        ("summary", "Generate a PR/MR summary"),
        ("full", "Run both review and summary"),
    ]:
        sub = subparsers.add_parser(
            name,
            help=help_text,
            parents=[common_parser],
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )
        _add_repo_arg(sub)

    subparsers.add_parser("config", help="Re-run interactive model/provider setup")

    args = parser.parse_args(_preprocess_argv(argv))

    # Config command — no repo/pr needed
    if args.command == "config":
        args.review = False
        args.summary = False
        return args

    # Detect PR/MR URL and extract platform, repo, pr, api_url
    if hasattr(args, "repo") and args.repo and args.repo.startswith(("https://", "http://")):
        try:
            platform, repo, pr, api_url = _parse_pr_url(args.repo)
        except argparse.ArgumentTypeError as e:
            parser.error(str(e))
        args.platform = platform
        args.repo = repo
        args.pr = pr
        if api_url:
            os.environ["GITLAB_HOST"] = api_url

    if args.command in ("review", "summary", "full") and args.pr is None:
        parser.error("-p/--pr is required when not using a PR/MR URL")

    # Map subcommand to review/summary booleans
    if args.command == "review":
        args.review = True
        args.summary = False
    elif args.command == "summary":
        args.review = False
        args.summary = True
    elif args.command == "full":
        args.review = True
        args.summary = True

    return args
