# ADR 0001 — Three-Tier Architecture

**Date:** 2026-06-14
**Status:** Accepted

## Context

We need to build a Task Manager application that demonstrates clean separation of concerns across three tiers: presentation, business logic, and data storage. The lab must also be teachable to students of mixed skill levels using Claude Code as an AI pair programmer throughout the delivery lifecycle.

## Decision

We adopt a **three-tier architecture**:

| Tier | Technology | Responsibility |
|------|-----------|----------------|
| Frontend | React 18 + TypeScript (Vite) | User interface and UX |
| Business Logic | FastAPI (Python 3.12) | API, validation, business rules, auth |
| Data | PostgreSQL 16 | Persistent storage |

All services run locally via Docker Compose. GitHub Actions enforces lint, type-check, and test coverage gates on every push.

## Rationale

- **React + FastAPI + PostgreSQL** is a widely-used, well-documented stack with strong Claude Code understanding, making AI-assisted suggestions more accurate.
- **Separation of tiers in distinct services** (not a monolith) teaches students about service boundaries and network communication.
- **Business logic in the API layer** (not stored procedures) keeps the rules testable in Python without a database.
- **Docker Compose** gives every student a consistent environment regardless of OS.

## Diagram

See [`docs/diagrams.md`](../diagrams.md) for the full architecture diagram, use case diagram, sequence diagrams, class diagram, and ER diagram.

## Consequences

- Students must understand both Python and TypeScript — the lab scaffolds this with starter code.
- Local-only deployment keeps the lab simple; students can add cloud deploy as an extension exercise.
- The clear boundary between tiers makes it easy to swap one tier (e.g., change frontend framework) as an advanced exercise.
