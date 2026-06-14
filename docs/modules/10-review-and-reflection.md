# Module 10 — Code Review & Reflection

## Learning Objectives

- Experience professional code review from both sides (author and reviewer)
- Use Claude Code skills to prepare a PR that is ready for human review
- Apply security review as a standard part of the development workflow
- Reflect honestly on where AI assistance helped and where it fell short

## Part A — Prepare Your Pull Request

Before opening a PR, run the full pre-merge checklist. These are the same checks CI will run:

### Quality gate
```
/check-standards
```

This runs all linters, both test suites, and the Docker build. Fix any failures before proceeding.

### Security gate
```
/security-scan
/check-secrets
```

Fix any HIGH or CRITICAL findings. For MEDIUM findings you choose to accept, add a comment in the code explaining the trade-off.

### Convention review
```
/review-conventions
```

Fix any layer boundary violations (router doing business logic, repository raising HTTPException, etc.).

### Open the PR

When all checks pass:

```bash
git push -u origin develop
```

Open a PR from `develop` → `main` on GitHub. Fill in every section of the PR template. Your PR must:
- Reference the modules it covers
- List the test commands the reviewer should run
- Have a passing CI pipeline (all four jobs: backend, frontend, security, docker-build)

## Part B — Peer Code Review

Your instructor will pair you with another student. As the **reviewer**:

```bash
# Check out their branch locally
git fetch origin
git checkout their-feature-branch

# Run the full review suite
/check-standards         # check quality gate passes on their code
/security-review         # OWASP Top 10 review of their implementation
/review-conventions      # check layer boundaries and naming conventions
```

Or for a GitHub PR review:
```bash
/code-review              # AI review in your terminal
/code-review --comment    # posts findings directly to the GitHub PR
```

Post at least **3 substantive review comments**. "Looks good" is not a review. Each comment should either:
- Identify a correctness or security issue
- Suggest a simplification
- Ask a clarifying question about a design decision

**Security-focused reviewer prompts:**
> "Run `/security-review` on the branch. Are there any OWASP findings the author didn't address?"
> "Does the `/check-secrets` output show any credential patterns in tracked files?"
> "Are there places where a status transition could be bypassed by calling the API directly (bypassing the frontend)?"
> "Does the test coverage cover the error paths — 401, 403, 422 — or only the happy path?"

**Architecture-focused reviewer prompts:**
> "Is the error handling in the router consistent with the OpenAPI spec?"
> "Does the test coverage cover the edge cases in the status machine?"
> "Are there any layer boundary violations where business logic leaked into the router?"

## Part C — Respond to Review

As the **author**, respond to every comment:
- If you agree → fix it and reply explaining what you changed
- If you disagree → explain your reasoning (declining a suggestion with a good reason scores higher than silently implementing everything)

For security findings you can't fix in this PR: create a GitHub Issue for each one and reference it in your reply.

## Part D — Reflection Report

Fill in `docs/reflection.md`. Target 400–600 words. Be honest — the most valuable reflections acknowledge what Claude Code got *wrong* or where it led you down a path you had to backtrack from.

**Grading tip:** A reflection that says "Claude Code was amazing and helped me do everything perfectly" scores lower than one that says "Claude Code suggested X which I initially followed, but when I tested it I found Y, so I did Z instead."

The reflection template in `docs/reflection.md` includes a section on security findings — describe at least one security issue the `/security-review` or `/security-scan` found that you hadn't noticed yourself.

## Checkpoint

- [ ] `/check-standards` passes with all green on your branch
- [ ] `/security-scan` shows no HIGH or CRITICAL findings (or you've documented accepted risks)
- [ ] PR is open on GitHub with all template sections filled in
- [ ] CI is green on your PR (all four jobs)
- [ ] You gave at least 3 substantive review comments on your peer's PR (including at least 1 security-focused comment)
- [ ] You responded to all comments on your own PR
- [ ] `docs/reflection.md` is committed (400–600 words, includes a security finding)

---

## Congratulations

You've completed the AI-Assisted DevOps lab. You've practiced:

- **Architecture design** — using Claude Code as a design partner, not just a code generator
- **API-first development** — OpenAPI spec written before implementation
- **Professional git workflow** — Conventional Commits, PR templates, branch protection
- **Three-tier application** — React + FastAPI + PostgreSQL with a clean layered architecture
- **Full observability** — structured logging with trace correlation, Prometheus metrics, Jaeger distributed traces, Grafana dashboards
- **Test-driven quality** — ≥70% coverage enforced by CI across both backend and frontend
- **E2E testing** — Playwright browser tests covering the critical user journey
- **Shift-left security** — OWASP review, STRIDE threat modeling, automated SAST and CVE scanning in pre-commit hooks and CI
- **Peer code review** — AI-assisted review with `/code-review` and `/security-review`

These practices are the same ones used by professional engineering teams shipping production software. The difference is now you have an AI pair programmer — and a suite of AI-powered quality and security tools — to accelerate every step.
