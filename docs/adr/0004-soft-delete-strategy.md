# ADR 0004 — Soft Delete Strategy and GDPR Compliance

**Date:** 2026-06-14
**Status:** Accepted

## Context

The Task Manager must handle record deletion for two distinct reasons:

1. **User-initiated deletion** — a user deletes a project or task they own
2. **GDPR right to erasure** — a user requests deletion of their account

In both cases we need to decide whether to physically remove the row from the database (hard delete) or mark it as deleted without removing it (soft delete).

## Decision

All deletions are **soft deletes**: a `deleted_at TIMESTAMPTZ` column is added to every domain model table (`users`, `projects`, `tasks`, `comments`). When a record is "deleted", the application sets `deleted_at = now(UTC)` instead of issuing a SQL `DELETE`.

All application-layer `SELECT` queries filter `WHERE deleted_at IS NULL`. Soft-deleted records are invisible to the API but retained in the database.

## Rationale

### Audit trail requirement

Regulatory environments (SOC 2, ISO 27001, PCI-DSS) require an audit trail of all data changes. Hard deletes destroy the evidence. Soft deletes preserve the history of what existed and when it was removed.

### GDPR Article 17 — Right to erasure

GDPR Article 17 grants individuals the right to request erasure of their personal data. However, GDPR also permits retention for legal, regulatory, or contractual obligations (Article 17(3)).

Our approach:
- The `DELETE /auth/users/me` endpoint soft-deletes the user record — the user can no longer log in, and their tokens are rejected
- The user's email, name, and hashed password are retained in the database until a hard purge is run after the legal retention window (default: 90 days)
- Operators can run a scheduled hard-delete to purge records where `deleted_at < NOW() - INTERVAL '90 days'`

This satisfies GDPR's right to erasure in spirit: the user is immediately unable to use the service, and their data is not used by the application. The retention window allows compliance with legal hold requirements.

### Referential integrity and cascades

Hard deletes on parent records (users, projects) would cascade to child records (tasks, comments), permanently destroying data. Soft deletes prevent accidental cascade destruction and allow recovery if a delete was issued in error.

### Implementation simplicity

All four repositories implement the same pattern: filter `deleted_at IS NULL` on reads; set `deleted_at = datetime.now(UTC)` on deletes. No triggers, no shadow tables, no event sourcing required.

## Trade-offs and Risks

| Risk | Mitigation |
|------|-----------|
| Soft-deleted rows accumulate indefinitely | Scheduled hard-purge after retention window (90 days default) |
| `deleted_at IS NULL` filter on every query has a performance cost at scale | `deleted_at` is indexed; cost is O(log n) per query |
| Developers forget to add the filter to new queries | `/check-db` skill reviews repository queries for missing soft-delete filters |
| Soft-deleted users' email is retained — re-registration with same email is blocked | By design; prevents account reuse after GDPR erasure request |

## Consequences

- All four model tables have a `deleted_at` column with an index
- All repository `SELECT` queries must include `WHERE deleted_at IS NULL` — violation is a convention error caught by `/review-conventions`
- Hard `DELETE` SQL is never used in application code — use soft delete instead
- Operators must implement a scheduled purge job for GDPR compliance in production deployments
- The `DELETE /auth/users/me` endpoint satisfies GDPR Article 17 in the context of this application
