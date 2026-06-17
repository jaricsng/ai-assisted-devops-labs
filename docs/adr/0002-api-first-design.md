# ADR 0002 — API-First Design with OpenAPI

**Date:** 2026-06-14
**Status:** Accepted

## Context

The frontend and backend are developed independently. We need a contract that both sides can work against without being blocked by each other's implementation progress.

## Decision

We write the **OpenAPI 3.1 specification first** (`docs/api/openapi.yaml`) before implementing any endpoints. The spec is the source of truth:

- Backend Pydantic schemas are derived from (or match) the spec
- Frontend TypeScript types are generated from the spec via `openapi-typescript`
- The FastAPI `/docs` Swagger UI must match the spec at all times

## Rationale

- Contract-first development prevents mismatches between frontend and backend
- Auto-generated TypeScript types eliminate a whole class of integration bugs
- The spec is human-readable — designers and product owners can review it without reading code
- Claude Code can generate both implementation stubs and tests from a spec

## Consequences

- Any endpoint change requires updating `openapi.yaml` first (enforced by PR review checklist)
- Students learn to think about API design before writing implementation code
- The spec serves as living documentation that never goes stale
- Spec drift is caught by the `/compliance-check` Domain 10 (Documentation) gate, which verifies the spec exists, is parseable, and cross-references it against the running API's route list
- The strict CSP (`default-src 'none'`) on the API blocks Swagger UI's inline scripts at `/docs` — documented as an accepted trade-off in ADR 0003; relax CSP for the `/docs` path in production if Swagger access is needed
