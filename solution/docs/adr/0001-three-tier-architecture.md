# ADR 0001 — Three-Tier Architecture

**Date:** 2026-06-14  
**Status:** Accepted

## Context

We need to choose an architectural pattern for the Task Manager application. The application has a UI for end users, business logic (task status transitions, ownership rules), and persistent data (projects, tasks, comments, users).

The options considered were:

1. **Monolith** — all code in one Python service, templates rendered server-side
2. **Three-tier** — React SPA / FastAPI service / PostgreSQL database, deployed as separate Docker containers
3. **Microservices** — separate services for auth, projects, tasks, notifications

## Decision

We chose the **three-tier architecture** with:
- **Presentation tier:** React 18 + TypeScript SPA (Vite) served by nginx in production
- **Logic tier:** FastAPI (Python 3.12) with a layered internal structure (Router → Service → Repository)
- **Data tier:** PostgreSQL 16 managed via SQLAlchemy async ORM + Alembic migrations

## Consequences

**Positive:**
- Clear separation of concerns — the UI can be developed and tested independently of the API
- FastAPI's async model handles concurrent requests efficiently without thread overhead
- The layered internal structure (Router / Service / Repository) prevents business logic from leaking into HTTP handlers or database queries
- PostgreSQL's relational model fits the domain naturally (projects own tasks, tasks own comments, foreign keys enforce referential integrity)

**Negative:**
- Two separate build pipelines (Python and Node) increase CI complexity
- CORS configuration is required and adds a class of potential security misconfiguration
- Local development requires Docker Compose to run all three tiers together

**Trade-off not taken:**
Microservices would add operational complexity (service discovery, distributed tracing becomes mandatory, multiple deployments) that is not justified for a team-sized application. The three-tier monolith with internal layering gives us most of the maintainability benefits without the operational overhead.
