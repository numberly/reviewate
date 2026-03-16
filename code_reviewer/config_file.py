"""Config file reader/writer for ~/.reviewate/config.toml

Stores model preferences and auth mode. API keys come from env vars.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

_console = Console(highlight=False)

CONFIG_PATH = Path.home() / ".reviewate" / "config.toml"

# Default models for Anthropic: (review, utility)
ANTHROPIC_DEFAULTS = ("claude-sonnet-4-6", "claude-haiku-4-5")


# =============================================================================
# Config file I/O
# =============================================================================


def load_config_file(path: Path = CONFIG_PATH) -> dict[str, object] | None:
    """Load config from TOML file. Returns None if file doesn't exist."""
    if not path.is_file():
        return None
    with open(path, "rb") as f:
        return tomllib.load(f)


def save_config_file(data: dict[str, object], path: Path = CONFIG_PATH) -> None:
    """Write config dict to TOML file (simple key=value serialization)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for section, values in data.items():
        lines.append(f"[{section}]")
        if isinstance(values, dict):
            for key, val in values.items():
                lines.append(f'{key} = "{val}"')
        lines.append("")
    path.write_text("\n".join(lines))


def get_config_model(tier: str, data: dict[str, object]) -> str | None:
    """Get 'provider/model' string for a tier from config data."""
    models = data.get("models")
    if not isinstance(models, dict):
        return None
    val = models.get(tier)
    return str(val) if val else None


def get_config_url(provider: str, data: dict[str, object]) -> str | None:
    """Get custom API URL for a provider from config data."""
    urls = data.get("urls")
    if not isinstance(urls, dict):
        return None
    val = urls.get(provider.lower())
    return str(val) if val else None


def get_config_auth(data: dict[str, object]) -> str | None:
    """Get auth mode from config data ('api_key', 'oauth', or 'custom')."""
    auth = data.get("auth")
    if not isinstance(auth, dict):
        return None
    val = auth.get("mode")
    return str(val) if val else None


# =============================================================================
# Interactive setup wizard
# =============================================================================


def _run_interactive_setup() -> dict[str, object]:
    """Prompt for auth mode and model choices. Save to config file."""
    _console.print()
    _console.print(
        Panel(
            "Reviewate uses two model tiers:\n"
            "  [bold]Review tier[/]  — code analysis, fact-checking (needs strong reasoning)\n"
            "  [bold]Utility tier[/] — formatting, parsing (fast & cheap is fine)",
            title="[bold]Welcome to Reviewate![/]",
            expand=False,
        )
    )
    _console.print()

    # --- Step 1: Auth mode ---
    _console.print("  [bold]Step 1 — How do you want to authenticate?[/]")
    _console.print("    [bold cyan]1[/]) Anthropic API key")
    _console.print("    [bold cyan]2[/]) Claude Code subscription (OAuth)")
    _console.print("    [bold cyan]3[/]) Custom endpoint (llama.cpp, LiteLLM, vLLM, etc.)")
    _console.print()

    choice = ""
    while choice not in ("1", "2", "3"):
        choice = Prompt.ask("  Pick a number").strip()

    auth_mode = {"1": "api_key", "2": "oauth", "3": "custom"}[choice]
    provider = "custom" if auth_mode == "custom" else "anthropic"
    urls: dict[str, str] = {}

    # Check existing env vars for API key / OAuth
    if auth_mode == "api_key":
        if os.getenv("ANTHROPIC_API_KEY"):
            _console.print("  [green]ANTHROPIC_API_KEY detected.[/]")
        else:
            _console.print("\n  [yellow]Set your API key before running:[/]")
            _console.print("    [dim]export ANTHROPIC_API_KEY=your-key[/]")

    elif auth_mode == "oauth":
        if os.getenv("CLAUDE_CODE_OAUTH_TOKEN"):
            _console.print("  [green]CLAUDE_CODE_OAUTH_TOKEN detected.[/]")
        else:
            _console.print("\n  [yellow]Generate a token with:[/]")
            _console.print("    [dim]claude setup-token[/]")
            _console.print("  [yellow]Then set it:[/]")
            _console.print("    [dim]export CLAUDE_CODE_OAUTH_TOKEN=your-token[/]")

    elif auth_mode == "custom":
        url = ""
        while not url:
            url = Prompt.ask("  API base URL (e.g. http://localhost:8080)").strip()
        urls["custom"] = url
        if not os.getenv("ANTHROPIC_API_KEY"):
            _console.print("\n  [yellow]Set your API key for the custom endpoint:[/]")
            _console.print("    [dim]export ANTHROPIC_API_KEY=your-key[/]")

    # --- Step 2: Models ---
    _console.print("\n  [bold]Step 2 — Review model[/]")
    review_model = _prompt_model("Review model", provider, tier="review")

    _console.print("\n  [bold]Step 3 — Utility model[/]")
    utility_model = _prompt_model("Utility model", provider, tier="utility")

    # Build and save config
    review_full = f"{provider}/{review_model}"
    utility_full = f"{provider}/{utility_model}"

    data: dict[str, object] = {
        "auth": {"mode": auth_mode},
        "models": {"review": review_full, "utility": utility_full},
    }
    if urls:
        data["urls"] = urls
    save_config_file(data)

    _console.print(f"\n  [green]Saved to {CONFIG_PATH}[/]")
    _console.print()
    return data


def _prompt_model(label: str, provider: str, tier: str = "review") -> str:
    """Prompt for a model name with optional defaults."""
    default_model = None
    if provider == "anthropic":
        default_model = ANTHROPIC_DEFAULTS[0] if tier == "review" else ANTHROPIC_DEFAULTS[1]
        _console.print(
            f"  [dim]We recommend [bold]{default_model}[/bold]. Press Enter to use it.[/]"
        )
    while True:
        model = Prompt.ask(f"  {label}", default=default_model or "").strip()
        if model:
            return model
