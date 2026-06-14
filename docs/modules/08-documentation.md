# Module 8 — Documentation

## Learning Objectives

- Write documentation that helps the next developer, not just the current one
- Use Claude Code to generate docstrings and README content — then review and improve them
- Understand that the OpenAPI Swagger UI *is* the API documentation
- Leave the project in a state where a new contributor can be productive in under 10 minutes

## What Good Documentation Looks Like

| Type | Lives in | Audience |
|------|----------|----------|
| `README.md` | Repo root | Anyone arriving for the first time |
| `CONTRIBUTING.md` | Repo root | Developers who want to contribute |
| `docs/adr/` | Version-controlled | Future decision-makers ("why is it this way?") |
| `docs/api/openapi.yaml` | Version-controlled | Frontend devs, API consumers |
| Function docstrings | Source code | IDE users, code reviewers |
| `CLAUDE.md` | Repo root | Claude Code (your AI pair programmer) |

## Activities

### 1. Audit the README

Read `README.md` as if you've never seen this project. Ask Claude Code:
> "Pretend you're a new student joining this project. Read README.md and tell me: what's missing? What questions would you have after reading it that the README doesn't answer?"

Fix at least two gaps. Common things students miss:
- How to reset the database (`docker compose down -v && docker compose up`)
- How to run a subset of tests (`pytest tests/test_task_service.py -v`)
- What happens if you forget to copy `.env.example`

### 2. Add docstrings to all service functions

The service layer is the most important code to document because it contains the non-obvious business rules.

Ask Claude Code:
> "Add Google-style docstrings to every public function in backend/app/services/task_service.py and backend/app/services/auth_service.py. Each docstring should explain WHY the function exists, not just WHAT it does. Include Args and Returns sections, and a Raises section where relevant."

Review what Claude Code writes. Edit any docstring where:
- It just restates the function name ("Validates the status transition" for `validate_status_transition`)
- It doesn't explain the business rule behind the check
- The Raises section is missing an exception that can actually be raised

**Good docstring example:**
```python
def validate_status_transition(current: TaskStatus, next_status: TaskStatus) -> None:
    """Enforce the task status state machine.

    Tasks follow a directed graph of valid transitions. Terminal states
    (DONE, CANCELLED) cannot be left — a task cannot be "un-done". This
    rule lives here, not in the router, so it applies regardless of how
    the task is updated (API, background job, seed script).

    Args:
        current: The task's current status.
        next_status: The requested next status.

    Raises:
        HTTPException: 422 if the transition is not in VALID_TRANSITIONS[current].
    """
```

### 3. Verify the Swagger UI matches the spec

Start the API:
```bash
docker compose up api
```

Open [http://localhost:8000/docs](http://localhost:8000/docs).

For each endpoint, verify:
- The request body matches `docs/api/openapi.yaml`
- The response schema matches the spec
- Error responses (404, 422, 401) are documented

Ask Claude Code:
> "Compare the /health endpoint in app/main.py with its definition in docs/api/openapi.yaml. Are they consistent? What's missing from the spec?"

Fix any discrepancies in the spec (the spec is the source of truth).

### 4. Update CLAUDE.md

Run `/init` to regenerate CLAUDE.md, or edit it manually to reflect what you've built:

Ask Claude Code:
> "Update CLAUDE.md to include: the status transition rules, the layered architecture (router → service → repository), the observability stack URLs, and any non-obvious commands a developer would need (like how to run a single test, apply migrations, or start the observability profile)."

Good CLAUDE.md entries help Claude Code give you better suggestions in future sessions because it understands your project's conventions. The current CLAUDE.md already includes:
- Observability stack URLs (Jaeger, Prometheus, Grafana)
- The full list of project skills (12 skills across standards and security)
- Layer architecture diagram
- Domain model and status machine rules
- Environment variable reference

Verify it still accurately reflects your implementation — if you added features or changed conventions, update CLAUDE.md to match.

### 5. Write your third ADR

Pick a documentation decision you made during this module. Options:
- "Why Google-style docstrings instead of NumPy or reST?"
- "Why OpenAPI 3.1 instead of 3.0?"
- "Why CLAUDE.md instead of a separate AI-instructions file?"

Write it as `docs/adr/0004-documentation-approach.md`.

## Checkpoint

- [ ] `README.md` answers: how to start the app, how to run tests, how to reset the DB, how to start the observability stack
- [ ] Every public function in `services/` has a docstring explaining the *why*
- [ ] The Swagger UI at `/docs` matches `docs/api/openapi.yaml` for every endpoint
- [ ] `CLAUDE.md` mentions the status transition rules, layered architecture, observability URLs, and available skills
- [ ] A third ADR is committed
- [ ] Commit: `docs: add service docstrings, update README and CLAUDE.md`

## The Documentation Test

Hand your `README.md` to someone who hasn't seen the project and ask them to get it running. If they need to ask you a question, that question should become a README update.
