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

Open `.github/workflows/ci.yml`. It has **four jobs** that run in parallel on every push and PR:

```
push / PR
  ├── backend   → black, isort, ruff, pytest (≥70% coverage)
  ├── frontend  → tsc --noEmit, eslint, vitest (≥70% coverage)
  ├── security  → bandit SAST, pip-audit CVEs, npm audit CVEs, secret grep
  └── docker-build → docker compose build (smoke test)

PR to main only:
  └── e2e       → Playwright full browser tests
```

All four must pass before a PR can merge to `main` (branch protection enforces this).

## The Security Job

The `security` job runs on every push — this is **shift-left security in CI**. It catches issues before a human reviewer ever sees the code:

| Step | Tool | What it catches |
|------|------|----------------|
| Python SAST | `bandit -r app/ -ll` | Hardcoded passwords, SQL injection patterns, dangerous function use |
| Python CVEs | `pip-audit` | Known vulnerabilities in Python dependencies |
| JS CVEs | `npm audit --audit-level=high` | High/critical vulnerabilities in npm packages |
| Secret scan | `grep` on tracked files | AWS keys, GitHub tokens, OpenAI keys matching known patterns |

The bandit step uses `--exit-zero` initially — it reports findings but doesn't fail the build. Once your team has triaged the baseline findings, remove `--exit-zero` to make it a hard gate.

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

The `security` job runs `bandit --exit-zero`, so it always passes but still reports findings. Read the output:

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

When you're satisfied the findings are understood and either fixed or accepted, remove `--exit-zero` from the bandit step in `ci.yml` to make it a hard gate.

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

### 5. Harden the bandit gate

When you're ready to make bandit a hard failure (not just informational):

1. Remove `--exit-zero` from the bandit step in `.github/workflows/ci.yml`
2. Run bandit locally to see all current findings: `cd backend && bandit -r app/ -c pyproject.toml -ll`
3. For each finding, either fix the code or add a `# nosec B<number>` comment with a justification:
   ```python
   subprocess.run(cmd)  # nosec B603 — cmd is fully controlled by internal code, never user input
   ```
4. Push and verify the security job passes with the hard gate

Ask Claude Code:
> "What's the risk of using `# nosec` to suppress a bandit finding? When is it appropriate and when is it a code smell?"

### 6. Set up branch protection

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

- [ ] All four CI jobs run on every push (check Actions tab)
- [ ] The `security` job reports bandit findings (check the Actions log)
- [ ] You've intentionally broken coverage CI and then fixed it
- [ ] You've seen the secret scan detect a pattern and understood why
- [ ] Coverage summary comment appears on PRs (Activity 4)
- [ ] Branch protection requires all four CI jobs on `main`
- [ ] Commit: `ci: add coverage comment; understand security gate`

## Extension: Add a Lint-on-Save Hook

If you haven't done this in Module 3, add a Claude Code hook so linting runs every time you save a Python file:

```
/update-config
```

> "Add a PostToolUse hook that runs `ruff check` on any Python file I write or edit."

This catches lint errors before you even open a PR, reducing CI feedback loops by catching issues at edit time rather than push time.
