# Contributing Guide

## Branch Strategy

```
main        ← protected; CI must pass; requires PR review; no direct commits
 └── develop ← integration branch; feature branches merge here
      ├── feature/add-task-filtering
      ├── feature/user-profile-page
      └── fix/status-transition-bug
```

- **Never commit directly to `main`** — the `no-commit-to-branch` pre-commit hook enforces this
- **Always branch from `develop`**, not `main`
- Branch names: `feature/<short-description>` or `fix/<short-description>`

---

## Commit Messages — Conventional Commits

Format: `<type>(<scope>): <description>`

```
feat(tasks): add status and priority filter query params
fix(auth): handle expired token gracefully in frontend
test(task-service): add coverage for CANCELLED→TODO guard
docs(adr): add ADR 0003 for Tanstack Query choice
chore(deps): bump fastapi to 0.115.4
ci(security): add bandit SAST to pipeline
```

Types: `feat` · `fix` · `test` · `docs` · `chore` · `refactor` · `ci` · `security`

Keep the description under 72 characters. Use imperative mood ("add", not "added").

---

## First-Time Setup

### 1. Install pre-commit hooks

```bash
pip install pre-commit
pre-commit install
```

### 2. Initialise the detect-secrets baseline

`detect-secrets` scans staged files for credential patterns. On first run it needs a baseline file that records any known false-positives:

```bash
pip install detect-secrets
detect-secrets scan > .secrets.baseline
git add .secrets.baseline
git commit -m "chore: initialise detect-secrets baseline"
```

After this, any newly added secret pattern that isn't in the baseline will block your commit.

### 3. Verify all hooks pass

```bash
pre-commit run --all-files
```

Expected output: all hooks pass green. If `bandit` flags an existing issue, fix it or add a `# nosec` comment with a justification.

---

## Pre-Commit Hooks

The `.pre-commit-config.yaml` runs these checks on every `git commit`:

| Hook | What it checks |
|------|---------------|
| `trailing-whitespace` | No trailing spaces |
| `end-of-file-fixer` | Files end with a newline |
| `check-yaml` / `check-json` | Valid YAML/JSON syntax |
| `check-merge-conflict` | No unresolved merge markers |
| `detect-private-key` | No PEM private keys in staged files |
| `no-commit-to-branch` | Blocks direct commits to `main` |
| `detect-secrets` | No API keys, passwords, or tokens (checks against `.secrets.baseline`) |
| `bandit` | Python SAST — blocks commits with medium+ severity security issues |
| `black` | Python code formatted to project style |
| `isort` | Python imports in correct order |
| `ruff` | Python lint rules |

If a hook fails and modifies a file (black, isort), re-stage the file and commit again:
```bash
git add <file>
git commit -m "your message"
```

---

## Code Standards

### Python (backend/)

- All functions must have type hints on parameters and return type
- Public functions must have a one-line docstring explaining the *why*, not the *what*
- No bare `except:` — always catch specific exceptions
- Use `Mapped[type]` annotations on all SQLAlchemy columns (2.0 style)
- Business logic goes in `services/`; SQL goes in `repositories/`; never mix layers

### TypeScript (frontend/)

- `strict: true` in tsconfig — no `any` (use `unknown` and narrow it)
- Prop types defined as explicit TypeScript interfaces, not inline types
- All API calls go through `src/api/` — never call `axios` or `fetch` directly from components
- Every data-fetching component handles loading, error, and success states
- Never hardcode the API base URL — always use `import.meta.env.VITE_API_URL`

### Database

- Schema changes must go through Alembic migrations — never edit the DB by hand
- Every foreign key column must have `index=True`
- `session.commit()` lives in the service layer, not inside repositories

### Security

- Never commit real secrets — `.env` is gitignored; use `.env.example` for templates
- Passwords hashed with bcrypt directly (`bcrypt.hashpw` / `bcrypt.checkpw`) — never MD5, SHA1, or plain text
- SQL queries use SQLAlchemy ORM — never f-string interpolation in SQL
- JWT secret comes from environment variable only; no hardcoded default in production

---

## Claude Code Skills

Use these skills to check and fix standards automatically. Type them in Claude Code:

```
/check-python         — check Python formatting and linting (read-only)
/fix-python           — auto-fix Python formatting issues
/check-frontend       — check TypeScript types and ESLint (read-only)
/fix-frontend         — auto-fix ESLint issues
/check-standards      — full pre-merge gate across all tiers
/review-conventions   — AI review of layer boundaries and project-specific rules
/check-db             — review models, migrations, and repository patterns
/security-scan        — automated SAST + CVE + secret pattern scan
/security-review      — OWASP Top 10 AI review
/check-secrets        — credential scan in tracked files and git history
/check-dependencies   — CVE audit for Python + JS packages
/threat-model         — STRIDE threat model for a feature or the whole app
```

---

## Pull Request Process

1. Create a branch from `develop`
2. Make your changes and write tests
3. Run the full quality check:
   ```bash
   # Using the skill (recommended):
   /check-standards

   # Or manually:
   cd backend && black --check . && isort --check . && ruff check . && pytest --cov-fail-under=70
   cd frontend && npm run typecheck && npm run lint && npm test
   ```
4. Run the security check before opening a PR to `main`:
   ```bash
   /security-scan
   /check-secrets
   ```
5. Open a PR using the PR template — fill in every section
6. Get at least one peer review before merging
7. Squash-merge or rebase-merge (no merge commits on `develop`)

---

## CI Pipeline

Every push and PR runs four parallel jobs. All must be green before a PR can merge to `main`.

| Job | Checks |
|-----|--------|
| `backend` | black, isort, ruff, pytest (≥70% coverage) |
| `frontend` | tsc, eslint, vitest (≥70% coverage) |
| `security` | bandit SAST, pip-audit CVEs, npm audit CVEs, secret pattern grep |
| `docker-build` | `docker compose build` smoke test |

E2E tests (Playwright) run only on PRs to `main`, not on every push, to keep feedback loops fast.
