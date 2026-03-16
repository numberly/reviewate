"""Tests for Config.from_env() with various env var combos."""

import os
from unittest.mock import patch

from code_reviewer.config import Config, _normalize_host


class TestConfigFromEnv:
    def test_empty_env(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("code_reviewer.config._detect_gitlab_host", return_value=None),
            patch("code_reviewer.config.load_config_file", return_value={}),
        ):
            config = Config.from_env()
        assert config.api_key is None
        assert config.oauth_token is None
        assert config.base_url is None
        assert config.review_model is None
        assert config.utility_model is None
        assert config.gh_token is None
        assert config.gitlab_token is None
        assert config.container_mode is False
        assert config.debug is False

    def test_anthropic_api_key(self):
        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-123"}, clear=True),
            patch("code_reviewer.config.load_config_file", return_value=None),
            patch("code_reviewer.config._detect_gitlab_host", return_value=None),
        ):
            config = Config.from_env()
        assert config.api_key == "sk-test-123"

    def test_oauth_token(self):
        with patch.dict(os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": "oauth-xyz"}, clear=True):
            config = Config.from_env()
        assert config.oauth_token == "oauth-xyz"

    def test_base_url_for_proxy(self):
        env = {
            "ANTHROPIC_API_KEY": "sk-test",
            "REVIEWATE_BASE_URL": "http://proxy:4000",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            patch("code_reviewer.config.load_config_file", return_value=None),
            patch("code_reviewer.config._detect_gitlab_host", return_value=None),
        ):
            config = Config.from_env()
        assert config.base_url == "http://proxy:4000"

    def test_base_url_anthropic_fallback(self):
        env = {
            "ANTHROPIC_API_KEY": "sk-test",
            "ANTHROPIC_BASE_URL": "http://legacy-proxy:4000",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            patch("code_reviewer.config.load_config_file", return_value=None),
            patch("code_reviewer.config._detect_gitlab_host", return_value=None),
        ):
            config = Config.from_env()
        assert config.base_url == "http://legacy-proxy:4000"

    def test_reviewate_model_env_overrides_config_file(self):
        env = {"REVIEWATE_REVIEW_MODEL": "opus", "REVIEWATE_UTILITY_MODEL": "haiku"}
        with (
            patch.dict(os.environ, env, clear=True),
            patch(
                "code_reviewer.config.load_config_file",
                return_value={
                    "models": {"review": "anthropic/sonnet", "utility": "anthropic/haiku"},
                },
            ),
        ):
            config = Config.from_env()
        assert config.review_model == "opus"
        assert config.utility_model == "haiku"

    def test_github_token(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_abc123"}, clear=True):
            config = Config.from_env()
        assert config.gh_token == "ghp_abc123"

    def test_github_token_fallback(self):
        with patch.dict(os.environ, {"GH_TOKEN": "ghp_fallback"}, clear=True):
            config = Config.from_env()
        assert config.gh_token == "ghp_fallback"

    def test_gitlab_token_and_host(self):
        env = {
            "GITLAB_TOKEN": "glpat-xyz",
            "GITLAB_HOST": "https://gitlab.example.com/api/v4",
        }
        with patch.dict(os.environ, env, clear=True):
            config = Config.from_env()
        assert config.gitlab_token == "glpat-xyz"
        assert config.gitlab_host == "https://gitlab.example.com/api/v4"

    def test_gitlab_access_token_fallback(self):
        with patch.dict(os.environ, {"GITLAB_ACCESS_TOKEN": "glpat-fallback"}, clear=True):
            config = Config.from_env()
        assert config.gitlab_token == "glpat-fallback"

    def test_container_mode(self):
        with patch.dict(os.environ, {"REVIEWATE_CONTAINER_MODE": "1"}, clear=True):
            config = Config.from_env()
        assert config.container_mode is True

    def test_container_mode_disabled(self):
        with patch.dict(os.environ, {"REVIEWATE_CONTAINER_MODE": "0"}, clear=True):
            config = Config.from_env()
        assert config.container_mode is False

    def test_debug_mode(self):
        with patch.dict(os.environ, {"REVIEWATE_DEBUG": "1"}, clear=True):
            config = Config.from_env()
        assert config.debug is True


class TestBuildAgentEnv:
    def test_empty_config(self):
        config = Config()
        env = config.build_agent_env()
        assert env == {}

    def test_api_key_only(self):
        config = Config(api_key="sk-test")
        env = config.build_agent_env()
        assert env == {"ANTHROPIC_API_KEY": "sk-test"}

    def test_full_config(self):
        config = Config(
            api_key="sk-test",
            oauth_token="oauth-xyz",
            base_url="http://proxy:4000",
            gh_token="ghp_abc",
            gitlab_token="glpat-xyz",
            gitlab_host="https://gitlab.example.com/api/v4",
        )
        env = config.build_agent_env()
        assert env["ANTHROPIC_API_KEY"] == "sk-test"
        assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "oauth-xyz"
        assert env["ANTHROPIC_BASE_URL"] == "http://proxy:4000"
        assert env["GITHUB_TOKEN"] == "ghp_abc"
        assert env["GITLAB_TOKEN"] == "glpat-xyz"
        assert env["GITLAB_HOST"] == "gitlab.example.com"

    def test_gitlab_host_normalized(self):
        config = Config(gitlab_host="https://gitlab.example.com/api/v4")
        env = config.build_agent_env()
        assert env["GITLAB_HOST"] == "gitlab.example.com"

    def test_none_values_excluded(self):
        config = Config(api_key="sk-test", gh_token=None)
        env = config.build_agent_env()
        assert "GITHUB_TOKEN" not in env


class TestNormalizeHost:
    def test_plain_hostname(self):
        assert _normalize_host("gitlab.example.com") == "gitlab.example.com"

    def test_https_url(self):
        assert _normalize_host("https://gitlab.example.com") == "gitlab.example.com"

    def test_https_url_with_path(self):
        assert _normalize_host("https://gitlab.example.com/api/v4") == "gitlab.example.com"

    def test_http_url(self):
        assert _normalize_host("http://gitlab.local:8080") == "gitlab.local"
