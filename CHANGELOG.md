# Changelog

## [1.1.0](https://github.com/numberly/reviewate/compare/v1.0.0...v1.1.0) (2026-03-16)


### Features

* initial release ([77730b2](https://github.com/numberly/reviewate/commit/77730b2fa39eaaae1ad51e65a933f85f913b5e3c))

## 1.0.0 (2026-03-16)

Initial release under [numberly/reviewate](https://github.com/numberly/reviewate).

### Features

* multi-agent review pipeline with parallel analyzers, fact checker, and style formatter
* summary pipeline for auto-generated PR/MR descriptions
* GitHub and GitLab support with inline review comments and webhooks
* self-hosted platform with dashboard, team management, and centralized configuration
* CLI tool (`pip install reviewate`) for local and CI usage
* two-tier model system for review and utility agents
* container isolation with Docker and Kubernetes backends
* gitleaks-based secret guardrail before posting
* CI integration for GitHub Actions and GitLab CI
* GitHub Enterprise and GitLab self-managed support
