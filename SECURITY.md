# Security Policy

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

If you discover a security vulnerability in Reviewate, please report it responsibly by emailing:

**<security@reviewate.com>**

### What to Include

- A description of the vulnerability
- Steps to reproduce the issue
- Potential impact assessment
- Any suggested fixes (optional)

### Response Timeline

| Action | Timeframe |
|--------|-----------|
| Acknowledgment of report | Within 48 hours |
| Initial assessment | Within 1 week |
| Fix development | Depends on severity |
| Public disclosure | After fix is released |

We will work with you to understand the issue and coordinate disclosure. We ask that you:

- Allow reasonable time for us to address the issue before public disclosure
- Make a good faith effort to avoid privacy violations, data destruction, or service disruption
- Do not access or modify other users' data

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest release | Yes |
| Previous releases | Security fixes only |

## Security Architecture

Reviewate handles code review, which is security-sensitive by nature. Key security measures include:

- **Container isolation** — Each code review runs in an isolated container that is destroyed after completion
- **No code persistence** — Reviewed code is never stored; containers are ephemeral
- **Network isolation** — Review containers cannot access the backend, database, or other containers
- **One-way communication** — The backend watches container logs via the container runtime API; containers cannot call back
- **Short-lived tokens** — Repository access uses short-lived tokens scoped to the specific review

For more details, see the [Security Architecture](README.md#secure-container-isolation) section in the README.

## Scope

The following are in scope for security reports:

- Authentication and authorization bypass
- Injection vulnerabilities (SQL, command, template)
- Container escape or isolation bypass
- Exposure of secrets, tokens, or credentials
- Cross-site scripting (XSS) or cross-site request forgery (CSRF)
- Data exposure or unauthorized access

The following are **out of scope**:

- Issues in third-party dependencies (report to the upstream project)
- Social engineering attacks
- Denial of service (DoS) attacks
- Issues requiring physical access

## Acknowledgments

We appreciate the security research community's efforts in helping keep Reviewate and its users safe. Responsible reporters will be credited in release notes (unless they prefer to remain anonymous).
