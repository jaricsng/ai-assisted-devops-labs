# Module 9 — CI/CD with GitHub Actions

## Learning Objectives

- Understand how the GitHub Actions pipeline enforces quality gates automatically
- Know what each CI job checks and why it matters
- Understand how the security job implements shift-left security in CI
- Add a new CI step yourself using Claude Code
- Configure branch protection rules that prevent bad code from reaching `main`

## Background

CI/CD ("Continuous Integration / Continuous Delivery") means:
- **CI:** Every push triggers automated checks — lint, type-check, test, security scan, build
- **CD:** Every passing merge to `main` could deploy automatically (we stop at CI in this lab)

The philosophy: **if it's not checked automatically, it will eventually be skipped.**

Manual quality checks → eventually forgotten under deadline pressure.
Automated quality gates → enforced on every commit, forever.

## The Pipeline

Open `.github/workflows/ci.yml`. It has **five jobs** that run in parallel on every push and PR:

```mermaid
flowchart LR
    push["push / PR"] --> B["backend\nblack · isort · ruff\npytest ≥70%"]
    push --> F["frontend\ntsc · eslint\nvitest ≥70%"]
    push --> S["security\nbandit · pip-audit\nnpm audit · secret grep"]
    push --> D["docker-build\ndocker compose build"]
    pr["PR to main\n(additionally)"] --> E["e2e\nPlaywright\nfull browser tests"]
```

All five must pass before a PR can merge to `main` (branch protection enforces this).

## The Security Job

The `security` job runs on every push — this is **shift-left security in CI**. It catches issues before a human reviewer ever sees the code:

| Step | Tool | What it catches |
|------|------|----------------|
| Python SAST | `bandit -r app/ -ll` | Hardcoded passwords, SQL injection patterns, dangerous function use |
| Python CVEs | `pip-audit` | Known vulnerabilities in Python dependencies |
| JS CVEs | `npm audit --audit-level=high` | High/critical vulnerabilities in npm packages |
| Secret scan | `grep` on tracked files | AWS keys, GitHub tokens, OpenAI keys matching known patterns |

The bandit step exits non-zero on any medium-or-above severity finding — it is a **hard gate**. If bandit finds an issue, the security job fails and the PR cannot merge. Fix the code or suppress with `# nosec B<number>` and a justification comment.

## Activities

### 1. Trigger the pipeline

Push a branch and watch all four jobs run:

```bash
git checkout -b ci/explore-pipeline
git commit --allow-empty -m "ci: trigger pipeline to observe all jobs"
git push -u origin ci/explore-pipeline
```

Open the **GitHub Actions** tab on your repo. Watch the four jobs run in parallel. Click into the `security` job and find:
- Where bandit reports its findings
- What CVE format pip-audit uses
- How the secret grep step works

Ask Claude Code:
> "Why does the security job run in parallel with the backend and frontend jobs rather than after them? What's the trade-off between speed and catching issues early?"

### 2. Understand the bandit findings

The `security` job runs `bandit -ll` (medium-and-above severity), which **fails the build** if any findings are present. Read the output locally:

```bash
# Run bandit locally to see the same output:
cd backend && bandit -r app/ -c pyproject.toml -ll
```

For each finding, bandit shows:
- **Severity** (LOW / MEDIUM / HIGH)
- **Confidence** (LOW / MEDIUM / HIGH)
- **CWE** — the Common Weakness Enumeration ID (links to the NIST database)
- **Location** — file and line number

Ask Claude Code about any finding:
> "Explain the bandit finding B105 at app/config.py:13. What's the attack vector and how should I fix it?"

For each finding, either fix the code or add a targeted suppression with justification:
```python
subprocess.run(cmd)  # nosec B603 — cmd is constructed from internal config, never user input
```

### 3. Make CI fail intentionally — then fix it

**Break the coverage gate:**
```python
# backend/app/services/task_service.py — add a function with no test coverage:
def placeholder_feature(x: int) -> int:
    """Placeholder for a future feature."""
    if x > 100:
        return x * 2
    elif x > 50:
        return x * 3
    else:
        return x
```

Push the branch — the `backend` job fails. Then ask Claude Code:
> "Write a pytest unit test for the placeholder_feature function that covers all three branches."

Add the test, push again — CI should pass. Clean up:
```bash
git revert HEAD HEAD~1 --no-edit
```

**Break the security gate:**

Add a pattern the secret grep recognises:
```bash
echo 'AKIAIOSFODNN7EXAMPLE = "test"' >> backend/app/main.py
git add backend/app/main.py
git commit -m "test: trigger secret scan"
git push
```

The `security` job's secret grep step should catch this. Revert it and observe the CI going green again.

### 4. Add a coverage summary comment to PRs

Ask Claude Code:
> "Add a GitHub Actions step to the backend job that posts the pytest coverage summary as a comment on the PR. Use the `MishaKav/pytest-coverage-comment` action. Show the complete updated job YAML."

Apply the change and push. Open a PR — the coverage report should appear as a comment.

> **Reference implementation:** `MishaKav/pytest-coverage-comment@v1.10.0` is already wired into the backend job in `.github/workflows/ci.yml` (pinned to a release tag, not `@main`, to reduce supply-chain risk).

### 5. Review and accept or fix bandit findings

Bandit is already a hard gate in this project (`--exit-zero` was removed). Your activity:

1. Run bandit locally: `cd backend && bandit -r app/ -c pyproject.toml -ll`
2. For each finding, decide: fix the code or suppress with justification:
   ```python
   subprocess.run(cmd)  # nosec B603 — cmd is constructed from internal config, never user input
   ```
3. Push and verify the security job passes

Ask Claude Code:
> "What's the risk of using `# nosec` to suppress a bandit finding? When is it appropriate and when is it a code smell?"

### 6. Review a Dependabot PR

The `.github/dependabot.yml` file is already configured to open weekly PRs for pip, npm, and GitHub Actions dependency updates. Dependabot is automated dependency hygiene — one of the cheapest security wins available.

When a Dependabot PR arrives:
1. Read the PR description — Dependabot links to the changelog or release notes
2. Check whether the update is a patch, minor, or major version bump
3. Look at the CI results — all jobs must pass before merging
4. For major version bumps, read the migration guide before approving
5. Merge the PR — or leave a comment explaining why you're deferring

Ask Claude Code:
> "A Dependabot PR bumped fastapi from 0.115 to 0.137. What changed between these versions that could affect this project? Check the changelog and identify any breaking changes."

> **Note:** Dependabot PRs appear on GitHub under the **Pull requests** tab. You don't need to do anything to enable them — the config file is already in the repo.

### 7. Set up branch protection


In your GitHub repo settings:
1. Go to **Settings → Branches → Add branch protection rule**
2. Branch name pattern: `main`
3. Enable:
   - ✅ Require a pull request before merging
   - ✅ Require status checks to pass — add: `backend`, `frontend`, `security`, `docker-build`
   - ✅ Require branches to be up to date before merging
   - ✅ Do not allow bypassing the above settings

Ask Claude Code:
> "What is the purpose of 'Require branches to be up to date before merging'? When would skipping this cause a problem even when all CI checks pass?"

## Understanding the Coverage Gate

The `--cov-fail-under=70` flag makes `pytest` exit non-zero if coverage drops below 70%. GitHub Actions treats any non-zero exit as failure. This means:

1. Developer writes code with no tests → coverage drops → CI fails → PR is blocked
2. Developer is forced to add tests before merging

The 70% threshold is a floor, not a target. Good tests cover behaviour, not just lines.

## Understanding the Security Gate

The security job implements the same principle for security issues:
1. Developer introduces a vulnerable dependency → pip-audit finds it → CI fails
2. Developer accidentally commits an API key → secret grep finds it → CI fails
3. Developer writes SQL with f-string interpolation → bandit finds it → CI reports it (fails once `--exit-zero` is removed)

This is shift-left security: **catching security issues at merge time rather than in production.**

## Checkpoint

- [ ] All six CI jobs visible in the Actions tab (`backend`, `frontend`, `security`, `docker-build`, `smoke-test`, `e2e`)
- [ ] The `security` job passes — bandit is a hard gate (no `--exit-zero`)
- [ ] You've intentionally broken coverage CI and then fixed it (Activity 3)
- [ ] You've seen the secret scan detect a pattern and understood why (Activity 3)
- [ ] Coverage summary comment appears on PRs (Activity 4)
- [ ] Bandit findings investigated — each either fixed or suppressed with `# nosec` + justification (Activity 5)
- [ ] Dependabot PRs reviewed and merged (Activity 6)
- [ ] Branch protection requires `backend`, `frontend`, `security`, `docker-build` on `main`
- [ ] Second CI run on same code is visibly faster due to pip + npm caching (Activity 8)
- [ ] Pushing a failing test shows `docker-build` and `smoke-test` as **Skipped**, not Failed (Activity 9)
- [ ] k6 smoke test passes on PRs to `main`; Playwright E2E only runs if smoke test passes (Activity 10)
- [ ] `CHANGELOG.md` created with `[Unreleased]` and `[0.1.0]` sections using Keep a Changelog format (Activity 11)
- [ ] `.github/workflows/drift-detection.yml` created — runs nightly to detect image/version drift and OpenAPI schema drift
- [ ] Commit: `ci: verify caching, job ordering, k6 smoke test, and CHANGELOG`

> **Reference implementations:** See `.github/workflows/drift-detection.yml` (nightly drift check with Slack alert) and the `slsa-provenance` + `notify-failure` jobs in `.github/workflows/publish.yml`.

### 8. Understand dependency caching

Without caching, every CI run reinstalls all packages from scratch — adding 60–90 seconds to every pipeline run. Open `ci.yml` and find the `backend` job:

```yaml
- name: Set up Python 3.12
  uses: actions/setup-python@v5
  with:
    python-version: "3.12"
    cache: "pip"
    cache-dependency-path: backend/pyproject.toml
```

The `cache: "pip"` option uses GitHub's built-in pip cache, keyed to the `pyproject.toml` hash — when dependencies change, the cache is invalidated automatically. The `frontend` job uses `cache: "npm"` on `setup-node` for the same reason.

Ask Claude Code:
> "Explain how `cache-dependency-path` works in `actions/setup-python`. What happens to the cache when I add a new package to `pyproject.toml`? What happens when I only change application code?"

Push a branch twice and compare the run times in the Actions tab. The second run should be 60+ seconds faster on the `backend` job.

### 9. Understand job dependency ordering with `needs:`

Open `ci.yml` and find the `docker-build` job:

```yaml
docker-build:
  name: Docker Compose build
  needs: [backend, frontend]   # only build images after tests pass — fail fast
```

The `needs:` key means `docker-build` is skipped entirely if `backend` or `frontend` fails. To verify:

1. Add a deliberate test failure to `backend/app/services/task_service.py`
2. Push the branch
3. Watch the Actions tab — `docker-build` shows as **Skipped** (grey), not **Failed** (red)

This is more informative than seeing it fail: grey means "we didn't reach this step because an earlier gate blocked it."

Ask Claude Code:
> "In GitHub Actions, what is the difference between a job that is `skipped` and one that `failed`? Can a downstream job with `if: always()` still run if an upstream job was skipped?"

### 10. Understand the k6 smoke test job

Open `ci.yml` and find the `smoke-test` job. It runs after `docker-build` on PRs to `main`:

```yaml
smoke-test:
  name: k6 smoke test
  needs: [docker-build]
  if: github.event_name == 'pull_request' && github.base_ref == 'main'
```

The smoke test starts the full Docker Compose stack and runs `load-tests/k6/smoke.js` using the k6 Docker image — no local k6 install required:

```bash
docker run --rm --network host \
  -v "${{ github.workspace }}/load-tests/k6:/scripts" \
  grafana/k6 run /scripts/smoke.js
```

The `e2e` job depends on `smoke-test` — Playwright only runs if k6 confirms the API is actually handling real requests correctly.

Ask Claude Code:
> "What is the difference between the k6 smoke test and the Playwright E2E tests in this pipeline? When would one pass but the other fail? Why run k6 first?"

This means any PR that breaks the full user journey (register → login → create project → create task) is caught before the slower Playwright suite even starts.

### 11. Create and maintain a CHANGELOG

A CHANGELOG is not just for users — it forces engineers to articulate *what changed and why* in each release, which is invaluable during incident investigation. The [Keep a Changelog](https://keepachangelog.com/) format is the industry standard.

Create `CHANGELOG.md` at the project root using the `[Unreleased]` → version pattern:

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-06-15

### Added
- Three-tier Task Manager application: FastAPI API, React frontend, PostgreSQL database
- JWT authentication with JTI revocation on logout
- Task status state machine: TODO → IN_PROGRESS → IN_REVIEW → DONE
- Seven HTTP security headers via SecurityHeadersMiddleware
- Structured audit logging on all write operations
- GDPR soft delete via `DELETE /auth/users/me`
- OpenTelemetry tracing → Jaeger; Prometheus metrics → Grafana
- E2E Playwright tests for critical user journeys
- OWASP pen test suite (22 checks)
- Docker Compose stack with observability profile

[Unreleased]: https://github.com/YOUR_USERNAME/task-manager/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/YOUR_USERNAME/task-manager/releases/tag/v0.1.0
```

**The release workflow**: every time you complete a module milestone and bump the version in `backend/pyproject.toml`, add a new dated version block to `CHANGELOG.md` moving items from `[Unreleased]`.

Ask Claude Code:
> "Read the git log since the project started (`git log --oneline`). Based on the commit messages, generate a CHANGELOG.md entry for version 0.1.0 using the Keep a Changelog format. Group commits by: Added, Changed, Fixed, Security."

### 12. Pipeline failure notifications

By default, GitHub notifies the PR author when CI fails. For team-wide visibility, add a Slack or email notification on `main` branch failures:

Ask Claude Code:
> "Add a notification step to the `backend` job that posts a Slack message when the job fails on the `main` branch. Use the `slackapi/slack-github-action` action. Use a `SLACK_WEBHOOK_URL` repository secret. Only notify on failure, only on `main`."

This is the pattern:
```yaml
- name: Notify Slack on failure
  if: failure() && github.ref == 'refs/heads/main'
  uses: slackapi/slack-github-action@v1
  with:
    payload: '{"text": "CI failed on main: ${{ github.workflow }} — ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"}'
  env:
    SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

## Extension: Add a Lint-on-Save Hook

If you haven't done this in Module 3, add a Claude Code hook so linting runs every time you save a Python file:

```
/update-config
```

> "Add a PostToolUse hook that runs `ruff check` on any Python file I write or edit."

This catches lint errors before you even open a PR, reducing CI feedback loops by catching issues at edit time rather than push time.
