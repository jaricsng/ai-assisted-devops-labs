# Module 3 — Git Workflow & Project Scaffolding

## Learning Objectives

- Set up professional git hygiene from the first commit
- Use Conventional Commits for a readable git log
- Configure pre-commit hooks so bad code and secrets never reach the repo
- Understand shift-left security: catching issues at commit time, not after merge
- Configure `.editorconfig` so every contributor produces consistent file formatting regardless of editor
- Create a `CODEOWNERS` file so security-sensitive paths get automatic reviewers on every PR

## Activities

### 1. Initialize the repository

```bash
cd task-manager
git init
git add .
git commit -m "chore: initial project scaffold from lab starter"
```

Create the branch structure:
```bash
git checkout -b develop
git push -u origin develop
```

### 2. Install pre-commit hooks

```bash
pip install pre-commit detect-secrets
pre-commit install
```

The `.pre-commit-config.yaml` already defines all the hooks you need. Initialise the `detect-secrets` baseline (this records known false-positives so the hook doesn't block on them):

```bash
detect-secrets scan > .secrets.baseline
git add .secrets.baseline
git commit -m "chore: initialise detect-secrets baseline"
```

### 3. Understand what each hook does

Run all hooks against the entire repo to see what passes:
```bash
pre-commit run --all-files
```

| Hook | What it blocks |
|------|---------------|
| `detect-private-key` | PEM private keys committed accidentally |
| `no-commit-to-branch` | Direct commits to `main` |
| `detect-secrets` | API keys, passwords, tokens matching known patterns |
| `bandit` | Python code with medium+ severity security issues (SQL injection, hardcoded passwords, etc.) |
| `black` | Python code not formatted to project style |
| `isort` | Python imports not in canonical order |
| `ruff` | Python lint violations |

Ask Claude Code:
> "Explain what the 'shift-left' principle means in security. Why is blocking a secret at commit time better than detecting it during a code review or after deployment?"

### 4. Experience a blocked commit

Try committing a file with a detectable secret pattern:

```bash
# Create a temporary test file
echo 'API_KEY = "AKIAIOSFODNN7EXAMPLE"' > /tmp/test_secret.py
git add /tmp/test_secret.py 2>/dev/null || true

# Try to commit a file with an AWS key pattern
echo 'AWS_KEY = "AKIAIOSFODNN7EXAMPLE"' >> backend/app/config.py
git add backend/app/config.py
git commit -m "test: trigger detect-secrets"
# detect-secrets should block this commit
```

Notice the hook reports the file and pattern. Now revert:
```bash
git checkout backend/app/config.py
```

This is the shift-left principle: the secret never reached the repo.

### 5. Test the formatting hooks

```bash
# Intentionally break formatting
echo "x=1+2" >> backend/app/main.py
git add backend/app/main.py
git commit -m "test: trigger black"
# black reformats the file and blocks the commit
```

Re-stage and commit:
```bash
git add backend/app/main.py
git commit -m "test: pre-commit hooks verified"
git revert HEAD --no-edit  # clean up
```

### 6. Add an `.editorconfig` file

Without `.editorconfig`, every developer's editor applies different defaults: some use tabs, some spaces; some trim trailing whitespace, others don't. This causes noisy diffs and pre-commit failures on other people's machines.

Create `.editorconfig` at the project root:

```ini
root = true

[*]
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true
charset = utf-8

[*.py]
indent_style = space
indent_size = 4
max_line_length = 88

[*.{ts,tsx,js,jsx}]
indent_style = space
indent_size = 2
max_line_length = 100

[*.{json,yaml,yml,toml}]
indent_style = space
indent_size = 2

[*.md]
trim_trailing_whitespace = false
```

Most editors (VS Code, JetBrains, vim) respect `.editorconfig` automatically, either natively or via the [EditorConfig plugin](https://editorconfig.org/).

Ask Claude Code:
> "My `.editorconfig` sets `indent_size = 4` for Python and `indent_size = 2` for TypeScript. Are there any files in this project where the current indentation doesn't match these settings? Check `backend/app/main.py` and `frontend/src/App.tsx` as samples."

### 7. Create a `CODEOWNERS` file

`CODEOWNERS` automatically adds reviewers when specific files are changed in a PR. This is essential for security-sensitive paths — you don't want someone to modify `middleware/security_headers.py` without a security-aware review.

Create `.github/CODEOWNERS`:

```
# Global owner — reviews any file not matched below
*                                       @YOUR_GITHUB_USERNAME

# Security-sensitive: auth middleware, JWT validation, route guards
backend/app/middleware/               @YOUR_GITHUB_USERNAME
backend/app/routers/auth.py           @YOUR_GITHUB_USERNAME
backend/app/services/auth_service.py  @YOUR_GITHUB_USERNAME
backend/app/routers/deps.py           @YOUR_GITHUB_USERNAME

# Database migrations: irreversible in production without careful review
backend/alembic/                      @YOUR_GITHUB_USERNAME

# CI/CD pipelines: can execute arbitrary code in the GitHub environment
.github/workflows/                    @YOUR_GITHUB_USERNAME

# Cloud deployment manifests
aws/                                  @YOUR_GITHUB_USERNAME
infra/gcp/                            @YOUR_GITHUB_USERNAME
aspire/                               @YOUR_GITHUB_USERNAME
fly.toml                              @YOUR_GITHUB_USERNAME
azure.yaml                            @YOUR_GITHUB_USERNAME

# Security policy and pen test scripts
SECURITY.md                           @YOUR_GITHUB_USERNAME
pen-tests/                            @YOUR_GITHUB_USERNAME
```

Replace `@YOUR_GITHUB_USERNAME` with your GitHub handle.

For CODEOWNERS enforcement to work, branch protection must require a review from code owners (Settings → Branches → your `main` rule → enable "Require review from Code Owners").

Ask Claude Code:
> "Review `.github/CODEOWNERS`. Are there any security-sensitive paths in `backend/app/` that I've missed? What about the observability config — should changes to Grafana alert rules also require a code owner review?"

### 8. Configure a Claude Code hook (optional but instructive)

Ask Claude Code to add a hook that runs `black` automatically after it writes Python files:
> "Configure a PostToolUse hook in Claude Code settings that runs black on any Python file I write or edit."

Or use `/update-config` and describe what you want.

### 9. Write your first feature commit

Create a feature branch:
```bash
git checkout -b feature/add-task-filtering
```

Make a small change (e.g., add filter query params to `backend/app/routers/tasks.py`).

Before committing, run:
```bash
/check-secrets     # verify no credentials in the change
/check-python      # verify formatting and lint
```

Commit using Conventional Commits:
```bash
git commit -m "feat(tasks): add status and priority filter query params"
```

Open a pull request from `feature/add-task-filtering` → `develop`.

## Conventional Commits Reference

| Prefix | When to use |
|--------|-------------|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `test:` | Adding or updating tests |
| `docs:` | Documentation only |
| `chore:` | Build tooling, deps, config |
| `refactor:` | Code change that isn't a feature or fix |
| `ci:` | CI pipeline changes |
| `security:` | Security fixes or improvements |

## Checkpoint

- [ ] `pre-commit run --all-files` exits clean
- [ ] `.secrets.baseline` is committed
- [ ] `.editorconfig` committed with Python indent=4 and TypeScript indent=2 settings
- [ ] `.github/CODEOWNERS` committed with your GitHub username as owner of `backend/app/middleware/`, `backend/app/routers/auth.py`, `backend/alembic/`, and `.github/workflows/`
- [ ] `git log --oneline` shows at least 2 Conventional Commits
- [ ] You have a `develop` branch and at least one `feature/*` branch
- [ ] You've opened a PR using the PR template (all checkboxes visible)
- [ ] A direct commit to `main` was blocked by the `no-commit-to-branch` hook (try it)
- [ ] Commit: `chore: configure pre-commit hooks, editorconfig, and CODEOWNERS`
