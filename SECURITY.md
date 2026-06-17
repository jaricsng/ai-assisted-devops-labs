# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| main    | Yes       |

Only the current `main` branch receives security fixes. Older releases are unsupported.

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Report via [GitHub Private Security Advisories](https://github.com/jaricsng/claudecode-task-manager/security/advisories/new)
(Settings → Security → Advisories → New draft security advisory).

### Response SLA

| Severity | Acknowledgement | Patch + Advisory |
|----------|----------------|-----------------|
| Critical | 24 hours       | 7 days          |
| High     | 48 hours       | 14 days         |
| Medium   | 5 business days| 30 days         |
| Low      | Best effort    | Best effort     |

### What to include

- Description of the vulnerability and affected component
- Steps to reproduce or proof-of-concept
- Potential impact (data exposure, privilege escalation, etc.)
- Any suggested mitigations you are aware of

### Scope

In-scope:
- `backend/` — FastAPI application and authentication
- `frontend/` — React application
- `docker-compose.yml` and related infrastructure

Out of scope:
- Third-party dependencies (report upstream; we will patch once a fix is available)
- Issues without a realistic attack path

## Security Controls

- Passwords hashed with bcrypt (cost factor 12)
- JWT HS256 tokens with unique JTI for revocation
- Input validation and length limits on all API endpoints
- HTTP security headers (CSP, HSTS, X-Frame-Options, etc.)
- SQL injection prevention via SQLAlchemy ORM (no raw SQL)
- Rate limiting on authentication endpoints
- Soft deletes with GDPR account erasure endpoint
- Dependency scanning: bandit (SAST), pip-audit, npm audit, Trivy (container)
- Secrets scanning via detect-secrets pre-commit hook
