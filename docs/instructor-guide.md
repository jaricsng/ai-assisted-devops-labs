# Instructor Guide

## Lab Overview

This is a self-paced, 10-module lab. Students build a three-tier Task Manager using Claude Code at every step of the delivery lifecycle. The lab works for mixed skill levels — beginners will follow the instructions closely while advanced students should be encouraged to deviate, experiment, and extend.

**Estimated time:** 20–40 hours depending on student background.

## Before the Lab Starts

1. **Fork the starter repo** and push to your institution's GitHub org so students fork from there
2. **Set GitHub branch protection** on `main`: require 1 PR review + CI passing
3. **Create student pairings** for Module 10 peer review (do this before the lab, not after)
4. **Pre-seed a demo walkthrough** — run Module 0 yourself and record a 5-minute video showing the working app

## Common Student Pitfalls

| Problem | Root cause | Solution |
|---------|-----------|---------|
| `docker compose up` fails immediately | Docker Desktop not running | Check Docker status; restart Docker |
| `SECRET_KEY` missing error | `.env` not created from `.env.example` | `cp .env.example .env` and set a real key |
| pytest fails to import `aiosqlite` | Dev dependencies not installed | `pip install -e ".[dev]" aiosqlite` |
| Pre-commit blocks every commit | Black auto-formats the file, student doesn't re-stage | After black runs, `git add` the file again |
| CI fails on coverage | Student wrote feature code without tests | Show them `htmlcov/index.html` to find uncovered lines |
| 422 on status transition in tests | Test doesn't follow the valid transition path | Walk through `VALID_TRANSITIONS` in `task.py` |

## Assessment Grading Notes

### Working app (30%)
Run `docker compose up` in their repo. Test:
- Register and log in
- Create a project
- Create 3 tasks with different priorities
- Move a task through TODO → IN_PROGRESS → IN_REVIEW → DONE
- Add a comment to a task
- Verify the 422 on invalid transition (e.g., TODO → DONE directly)

Full marks if all of the above work. Deduct 5% per broken feature.

### GitHub repo quality (20%)
Check:
- `git log --oneline` — at least 10 commits, mostly Conventional Commits format
- At least 2 feature branches visible in the git history (merged PRs)
- PR template was used (check closed PRs)
- Meaningful commit messages (not "fix stuff" or "update")

### Test coverage (20%)
CI artifact shows coverage report. Must be ≥70% on both backend and frontend. Students who hit exactly 70% by writing trivial tests that don't verify behaviour — check the test quality, not just the number.

### Peer code review (15%)
Review the PR comments on GitHub. Full marks require:
- ≥3 substantive comments given (not "LGTM" or "+1")
- ≥1 response to received comments (engagement, not silence)
- Evidence they ran `/code-review` (ask them in the reflection)

### Reflection (15%)
Read `docs/reflection.md`. The rubric:
- **Full marks:** Includes a real example of disagreeing with Claude Code and explains the reasoning
- **Partial:** Lists examples of Claude Code helping but doesn't engage critically
- **Minimal:** Superficial ("Claude Code was helpful")

## Extension Exercises (for advanced students)

1. **Add task search** — implement `GET /projects/{id}/tasks?status=TODO&priority=HIGH` (spec already written in Module 2)
2. **Email notifications** — when a task is assigned, send an email via `fastapi-mail`
3. **Pagination** — add cursor-based pagination to the task list endpoint
4. **Cloud deploy** — deploy to Render or Railway using the existing Dockerfile
5. **E2E tests** — add Playwright tests that drive the React frontend against the real API
6. **Observability** — covered in **Module 05b**: structured JSON logging, request IDs, `/ready` probe, `/metrics` endpoint, OpenTelemetry tracing (extension)

## How to Extend the Lab

To add a new module:
1. Create `docs/modules/NN-topic.md` following the existing module format
2. Update the module table in `README.md`
3. If the module requires new starter code, add it to the scaffold

The lab is designed so each module is independently completable — students who get stuck on one module can skip ahead and return later.

## Claude Code Skills Used in This Lab

### Built-in Skills

| Skill | Module | Purpose |
|-------|--------|---------|
| `/init` | 0, 8 | Generate/update CLAUDE.md |
| `/update-config` | 3 | Configure pre-commit hook |
| `/code-review` | 10 | Peer review |
| `/code-review --comment` | 10 | Post review comments to GitHub PR |
| `/security-review` | 5 | Review auth implementation |

### Project Skills (`.claude/commands/`)

These custom skills are defined in the lab repo and are available the moment students clone it.

#### Coding Standards Skills

| Skill | Module | Purpose |
|-------|--------|---------|
| `/check-python` | 3, 5, 7 | Run black/isort/ruff — read-only report with explanations |
| `/fix-python [file]` | 3, 5 | Auto-apply black, isort, ruff --fix |
| `/check-frontend` | 6, 7 | Run tsc + ESLint — read-only report with explanations |
| `/fix-frontend [file]` | 6 | Auto-apply ESLint --fix; explain remaining manual fixes |
| `/check-standards` | 9, 10 | Full pre-merge gate: all linters + both test suites + Docker build |
| `/review-conventions` | 5, 7, 10 | AI review of layer boundaries, security, naming, git hygiene |
| `/check-db` | 4, 5 | Review SQLAlchemy models, Alembic migrations, repository patterns |

#### Security Skills (Shift-Left)

| Skill | Module | Purpose |
|-------|--------|---------|
| `/security-scan` | 5, 10 | Automated scan: bandit SAST + pip-audit + npm audit + secret patterns. Risk-ranked report. |
| `/security-review` | 5, 10 | AI OWASP Top 10 review mapped to this codebase. Finds logic-level issues tools miss. |
| `/check-secrets` | 3, 5 | Detect hardcoded credentials in tracked files and git history; verify .gitignore coverage. |
| `/check-dependencies` | 6, 9 | CVE audit for Python + JS packages; checks lock file hygiene and CI gap. |
| `/threat-model [feature]` | 1, 5 | STRIDE threat model for the app or a named feature. Produces a prioritised mitigation backlog. |

**Teaching tip — shift-left security:** Introduce `/check-secrets` in Module 3 (before the first real commit) and `/security-scan` in Module 5 (after auth is implemented). Run `/threat-model` in Module 1 as a design exercise before any code is written — this is the shift-left principle in action.

**Teaching tip — peer review:** Have students run `/security-review` on their own PR before the peer reviewer does. Students who find and fix issues themselves demonstrate deeper understanding than those who wait for the reviewer.
