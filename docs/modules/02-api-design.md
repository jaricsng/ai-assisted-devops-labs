# Module 2 — API Design (OpenAPI First)

## Learning Objectives

- Read and extend an OpenAPI 3.1 specification
- Understand why API design precedes implementation
- Validate an OpenAPI spec using CLI tooling

## Background

The `docs/api/openapi.yaml` file is the *source of truth* for the API contract between the frontend and backend. Both sides must match it. Any change to an endpoint requires a spec change first.

## Activities

### 1. Read the existing spec

Open `docs/api/openapi.yaml` and answer:
- How does a client authenticate? (Hint: look at `securitySchemes`)
- What HTTP status code does `PATCH /tasks/{id}` return for an invalid status transition?
- What fields are required when creating a task?

Ask Claude Code to check your understanding:
> "Quiz me on the Task Manager OpenAPI spec. Ask me 5 questions about the API design."

### 2. Validate the spec

```bash
npx @redocly/cli lint docs/api/openapi.yaml
```

All validation warnings should be zero. If any appear, fix them.

### 3. Extend the spec — add a search endpoint

Add a new endpoint to the spec: `GET /projects/{project_id}/tasks?status=TODO&priority=HIGH`

Think about:
- What query parameters should be optional vs. required?
- What response body should it return?
- Should this be a new path or a query parameter on the existing list endpoint?

Ask Claude Code:
> "I want to add filtering by status and priority to the task list endpoint. Should I use query parameters or a separate search endpoint? What are the trade-offs?"

After deciding, update `docs/api/openapi.yaml`. **Do not implement it yet** — we're still designing.

### 4. Design discussion

Ask Claude Code the following questions and note the answers in your ADR or a comment:
> "What HTTP status code should be returned when a task is moved to an invalid status?"
> "Should pagination be cursor-based or offset-based for this app, given 10–1000 tasks per project?"

## API Security Threat Checklist

Before moving to implementation, answer these 5 questions about your spec. If any answer is "no" or "unsure", it's a design gap — fix it in the spec now, not in production later.

1. **Authentication** — Are all write endpoints (POST/PATCH/DELETE) protected by a `security` requirement in the spec?
2. **IDOR risk** — Does any endpoint return data owned by another user if the caller supplies a different resource ID?
3. **Injection risk** — Does any path or query parameter flow directly into a database query or file path without validation?
4. **Error consistency** — Do all 401/403/404 responses return the same shape, with no difference that would let an attacker enumerate users or resources?
5. **Rate limiting** — Is any endpoint a high-value target (login, password reset, registration) that needs rate limiting?

> These 5 questions are the foundation of your threat model. You will expand them into a full STRIDE analysis in Module 19.

## Checkpoint

- [ ] You can explain every endpoint in the spec without help
- [ ] `npx @redocly/cli lint docs/api/openapi.yaml` exits clean
- [ ] You've added the filter query parameters to the spec for the task list endpoint
- [ ] You've committed the updated spec before writing any implementation code
- [ ] All 5 API security threat checklist questions answered — gaps documented as comments in the spec or in your ADR
