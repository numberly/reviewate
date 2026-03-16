# ADR-005: Skills System for Enhanced Code Review

**Status**: Proposed
**Date**: 2025-01-29

## Context

Reviewate currently supports project-specific context via:

- **CLAUDE.md / AGENTS.md**: Fetched from the repository being reviewed
- **Guidelines**: Text field in organization/repository settings (not yet passed to code_reviewer)

Users want to leverage **reusable knowledge modules** (skills) that encode domain expertise:

- Language conventions (Go idioms, Python best practices)
- Framework patterns (React hooks rules, Django security)
- Company standards (internal API conventions, error handling)
- Security rules (OWASP guidelines, auth patterns)

### Inspiration

Companies maintain "skills repositories" - git repos containing multiple skill definitions that can be shared across projects and teams. This pattern allows:

- Version-controlled knowledge that evolves with the codebase
- Reusable expertise across multiple repositories
- Collaborative improvement via PRs to skill definitions

### Requirements

1. **Clear separation**: Skills are NOT the same as CLAUDE.md or guidelines
2. **Git-based**: Skills live in git repositories (version controlled, shareable)
3. **Flexible format**: Support various skill repo structures (not enforce one format)
4. **Agent-driven selection**: The review agent decides which skills to use based on the code
5. **Minimal backend complexity**: Backend stores references only, code_reviewer fetches content
6. **Manifest injection**: Skill repo "meta-skills" (how to use the skills) are always injected

## Decision

### Architecture Overview

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                           CONTEXT HIERARCHY                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ALWAYS INJECTED (baseline context):                                    │
│  ├── CLAUDE.md / AGENTS.md    → From repo being reviewed                 │
│  ├── User guidelines         → From settings (text field)               │
│  └── Skill manifests         → From each skill repo (fetched by agent)  │
│                                                                         │
│  AGENT FETCHES ON DEMAND (via tools):                                   │
│  └── Individual skills       → list_skills() / fetch_skill(id)          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```text
┌─────────────────────────────────────────────────────────────────────────┐
│  BACKEND (stores references only)                                       │
│                                                                         │
│  Organization:                                                          │
│    guidelines: str              # Always injected                       │
│    skill_repos: ["github.com/acme/skills", ...]                         │
│                                                                         │
│  Repository (inherits/overrides org):                                   │
│    guidelines: str | None       # Override or append                    │
│    skill_repos: [...]           # Additional repos                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   │ ReviewJobMessage includes skill_repos
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  CODE REVIEWER                                                          │
│                                                                         │
│  1. Fetch CLAUDE.md from repo being reviewed (existing)                 │
│  2. Initialize SkillsManager with skill_repos list                      │
│  3. SkillsManager fetches manifests from each repo                      │
│  4. Manifests injected into agent context                               │
│  5. Agent uses list_skills() / fetch_skill() tools as needed            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Skill Repository Format (Flexible Detection)

The code_reviewer attempts multiple discovery strategies:

```text
Strategy 1: Manifest file (skills.yaml)
─────────────────────────────────────────
acme-skills/
├── skills.yaml           ← Manifest with skill list
├── SKILLS.md             ← Injected as context (how to use skills)
├── golang/
│   └── SKILL.md
└── security/
    └── SKILL.md

Strategy 2: Directory-based
─────────────────────────────────────────
acme-skills/
├── README.md             ← Injected as manifest
├── golang/
│   └── SKILL.md
└── security/
    └── SKILL.md

Strategy 3: Flat files
─────────────────────────────────────────
acme-skills/
├── README.md             ← Injected as manifest
├── golang.md             ← skill id = "golang"
└── security.md           ← skill id = "security"

Strategy 4: Single-skill repo
─────────────────────────────────────────
my-go-guidelines/
└── SKILL.md              ← Entire repo = one skill
```

### Manifest / Base Skill

Each skill repo should have a "meta-skill" that explains how to use the skills:

```markdown
# SKILLS.md (or README.md)

# Acme Engineering Skills

These skills encode our engineering standards.

## When to use:
- **golang**: Use for any Go code. Prioritize over generic advice.
- **security**: Always check for auth/input validation code.
- **api-patterns**: Use when reviewing HTTP handlers.

## Priorities:
When skills conflict: security > correctness > performance

## Philosophy:
We value readability over cleverness. Simple > smart.
```

This is **always injected** into the agent context - it's not fetched on demand.

### Agent Tools

```python
class SkillTools:
    """Tools for agents to discover and use skills."""

    async def list_skills(self) -> list[SkillMeta]:
        """
        List all available skills with descriptions.

        Returns:
            List of skills with id, name, description, source.
            Use this to understand what domain expertise is available.
        """
        ...

    async def fetch_skill(self, skill_id: str) -> str:
        """
        Fetch the full content of a skill.

        Args:
            skill_id: The skill identifier from list_skills()

        Returns:
            The skill content as markdown. Use this knowledge
            to inform your code review.
        """
        ...
```

### Guardrails

```python
MAX_SKILLS_PER_REVIEW = 5          # Prevent fetching everything
MAX_SKILL_SIZE_BYTES = 50_000      # ~50KB per skill
MANIFEST_CACHE_TTL = 3600          # Cache manifests for 1 hour
SKILL_CACHE_TTL = 3600             # Cache skill content for 1 hour
```

### Backend Model Changes

```python
# backend/api/models/organizations.py
class Organization(Base):
    guidelines: Mapped[str | None]           # Existing
    skill_repos: Mapped[list[str] | None]    # NEW: ["github.com/acme/skills"]

# backend/api/models/repositories.py
class Repository(Base):
    guidelines: Mapped[str | None]           # Existing (override)
    skill_repos: Mapped[list[str] | None]    # NEW: additional repos
```

### API Schema Changes

```python
# backend/api/routers/organizations/schemas.py
class OrganizationSettings(BaseModel):
    guidelines: str | None
    skill_repos: list[str] = []              # NEW
    automatic_review_trigger: str
    include_summary: bool

# backend/api/routers/repositories/schemas.py
class RepositorySettings(BaseModel):
    guidelines: str | None
    skill_repos: list[str] | None = None     # NEW (None = inherit)
    automatic_review_trigger: str | None
    include_summary: bool | None
```

### Job Message Changes

```python
# backend/api/routers/queue/schemas.py
class ReviewJobMessage(BaseModel):
    # ... existing fields ...

    # Review configuration (NEW)
    guidelines: str | None = None            # Merged org + repo guidelines
    skill_repos: list[str] = []              # Merged org + repo skill repos
```

### Code Reviewer Integration

```python
# code_reviewer/skills/manager.py
class SkillsManager:
    """Manages skill discovery, caching, and fetching."""

    def __init__(self, skill_repos: list[str]):
        self.repos = skill_repos
        self._manifests: list[SkillManifest] = []
        self._catalog: list[SkillMeta] = []
        self._cache: dict[str, str] = {}

    async def initialize(self) -> None:
        """Fetch manifests and build skill catalog."""
        for repo_url in self.repos:
            manifest = await self._fetch_manifest(repo_url)
            if manifest:
                self._manifests.append(manifest)

            skills = await self._discover_skills(repo_url)
            self._catalog.extend(skills)

    def get_injected_context(self) -> str:
        """Get manifests to inject into agent prompt."""
        if not self._manifests:
            return ""

        parts = ["<skill-manifests>"]
        for m in self._manifests:
            parts.append(f'<manifest source="{m.source}">')
            parts.append(m.content)
            parts.append("</manifest>")
        parts.append("</skill-manifests>")
        return "\n".join(parts)

    # Tool implementations
    async def list_skills(self) -> list[SkillMeta]:
        return self._catalog

    async def fetch_skill(self, skill_id: str) -> str:
        if skill_id in self._cache:
            return self._cache[skill_id]

        content = await self._do_fetch(skill_id)
        self._cache[skill_id] = content
        return content
```

### Prompt Template Updates

```jinja2
{# code_reviewer/prompts/review_agent.txt #}

{# Always injected context #}
{% if user_guidelines %}
<user-guidelines>
{{ user_guidelines }}
</user-guidelines>
{% endif %}

{% if skill_manifests %}
{{ skill_manifests }}
{% endif %}

{# Tools available #}
You have access to skill tools for domain-specific expertise:
- list_skills(): See available skills with descriptions
- fetch_skill(id): Get the full content of a skill

When reviewing code, consider fetching relevant skills based on:
- The programming languages in the diff
- The type of changes (security, API, frontend, etc.)
- Guidance from the skill manifests above
```

### Workflow Changes

```python
# code_reviewer/workflows/review.py

class ReviewWorkflow:
    def __init__(
        self,
        config: Config,
        repository: RepositoryHandler | None = None,
        issue_handler: IssueHandler | None = None,
        skill_repos: list[str] | None = None,        # NEW
    ):
        self.skill_repos = skill_repos or []
        self.skills_manager: SkillsManager | None = None

    async def run(self, ...) -> WorkflowResult:
        # Initialize skills
        if self.skill_repos:
            self.skills_manager = SkillsManager(self.skill_repos)
            await self.skills_manager.initialize()

        # Build context
        ctx = PipelineContext(...)
        ctx.user_guidelines = await self._fetch_user_guidelines(...)
        ctx.skill_manifests = (
            self.skills_manager.get_injected_context()
            if self.skills_manager else ""
        )

        # Pass tools to review agents
        skill_tools = self.skills_manager.get_tools() if self.skills_manager else None

        # ... rest of workflow
```

## Alternatives Considered

### 1. File Upload for Custom Skills

**Approach**: Allow users to upload skill files via frontend, store in database.

**Why deferred**:

- Adds storage burden to backend
- Skills lose version control benefits
- Harder to share across organizations
- Can add later if users strongly need it

### 2. Pre-configured Skill Selection

**Approach**: User explicitly selects which skills to use per repository.

**Why rejected**:

- Requires manual configuration for each repo
- User might not know which skills are relevant
- Agent is better positioned to decide based on actual code

### 3. Built-in Skills Registry

**Approach**: Ship Reviewate with built-in skills (security, performance, etc.).

**Why deferred**:

- Good to have eventually, but not MVP
- Focus first on user-provided skills
- Can add built-in skills as a default skill repo later

### 4. Skill Composition / Inheritance

**Approach**: Skills can reference other skills, build hierarchies.

**Why deferred**:

- Adds complexity
- Not needed for MVP
- Can explore later if users need it

## Consequences

### Positive

- **Clean separation**: Skills distinct from project guidelines
- **Version controlled**: Skills in git = history, collaboration, sharing
- **Flexible**: Supports various repo formats, agent decides what to use
- **Simple backend**: Just stores URL references
- **Intelligent selection**: Agent picks relevant skills per review
- **Extensible**: Easy to add more skill repos without code changes

### Negative

- **Network dependency**: Code reviewer must fetch from GitHub/GitLab
- **Cache complexity**: Need to cache manifests and skills appropriately
- **Discovery heuristics**: Flexible format detection may have edge cases
- **Agent trust**: Agent might miss relevant skills or fetch irrelevant ones

### Neutral

- **Git-only for v1**: Users need a git repo for skills (even single skill)
- **Public repos preferred**: Private repos need auth token handling

## Implementation Plan

### Phase 1: Core Infrastructure

1. Add `skill_repos` field to Organization and Repository models
2. Update API schemas and handlers
3. Add `skill_repos` to ReviewJobMessage
4. Database migration

### Phase 2: Code Reviewer Skills Manager

1. Create `code_reviewer/skills/` module
2. Implement SkillsManager with discovery strategies
3. Implement caching (in-memory for v1, Redis later)
4. Add skill tools to agent tool registry

### Phase 3: Agent Integration

1. Update PipelineContext with skill_manifests field
2. Pass skill tools to SimpleReviewAgent
3. Update prompt templates
4. Update workflow to initialize skills

### Phase 4: Frontend

1. Add skill_repos input to organization settings
2. Add skill_repos input to repository settings
3. Preview/validate skill repos before adding
4. Display discovered skills from each repo

## Open Questions

1. **Caching strategy**: In-memory vs Redis for skill content cache?
2. **Private repos**: How to handle auth tokens for private skill repos?
3. **Rate limiting**: How to handle GitHub API rate limits for skill fetching?
4. **Skill conflicts**: What if two skills give contradictory advice?

## References

- Current guidelines implementation: `code_reviewer/workflows/review.py:328-336`
- Repository model: `backend/api/models/repositories.py:67-75`
- Organization model: `backend/api/models/organizations.py`
- Job message schema: `backend/api/routers/queue/schemas.py`
