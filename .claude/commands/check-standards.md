Run the full pre-merge quality gate across all three tiers: Python linting, TypeScript type checking + ESLint, and both test suites with coverage. This is the same set of checks that CI runs — use it before opening a PR.

## Steps

Run all checks. Each step is independent — run them all even if earlier ones fail so you get a complete picture.

### 1. Python tier (backend/)

```bash
cd backend
black --check .
isort --check .
ruff check .
pytest --cov=app --cov-report=term-missing --cov-fail-under=70 -q
```

### 2. Frontend tier (frontend/)

```bash
cd frontend
npm run typecheck
npm run lint
npm test
```

### 3. Docker build smoke test (project root)

```bash
docker compose build --quiet
```

This confirms the Dockerfiles still produce valid images.

## Reporting

After all checks complete, produce a report in this format:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Standards check — Task Manager
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Python (backend/)
  black        ✅ / ❌
  isort        ✅ / ❌
  ruff         ✅ / ❌
  pytest (cov) ✅ / ❌  [XX% coverage]

Frontend (frontend/)
  tsc          ✅ / ❌
  eslint       ✅ / ❌
  vitest (cov) ✅ / ❌  [XX% coverage]

Docker build   ✅ / ❌

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Result: ✅ READY TO MERGE  /  ❌ X checks failed
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

For every ❌ item, list the failing details below the table with the exact command to fix it:
- Formatting failures → `run /fix-python` or `run /fix-frontend`
- Test coverage below 70% → show which files have the lowest coverage (from the term-missing report) and suggest which lines to test
- Type errors → show error with file:line and suggested fix
- Lint errors → show rule name, file:line, and one-line explanation

## Context

- Run from the project root (`task-manager/`)
- The Docker build step requires Docker Desktop to be running; skip it and note the skip if Docker is not available
- Coverage must be ≥70% on both backend and frontend — this is enforced by CI
- If the user passes `--no-docker` as an argument (`/check-standards --no-docker`), skip the Docker build step
