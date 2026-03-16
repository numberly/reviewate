---
applyTo: '**'
---

# Contribution Guidelines

- Never create summary or related md files explaining architecture or refactoring changes you made.
- Only make changes to architecture or refactoring documentation when explicitly instructed to do so.
- Never create visual diagrams or flowcharts.
- Always add error handling using ReviewateError, look at error.rs for context.
- Always run make qa and make test to ensure code quality and tests pass.
- For python use Annotated types from typing module for type hints.
- Ensure all new public methods and classes have docstrings.
- To run the frontend locally, `cd frontend && nvm use && pnpm dev`.
