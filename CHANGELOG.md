# Changelog

## [1.0.1](https://github.com/numberly/reviewate/compare/v1.0.0...v1.0.1) (2026-03-17)


### Bug Fixes

* use --filter for openapi-ts in generate-types ([#20](https://github.com/numberly/reviewate/issues/20)) ([6b1f0f1](https://github.com/numberly/reviewate/commit/6b1f0f1a300ec998d403fa48396044c243009c75))

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
