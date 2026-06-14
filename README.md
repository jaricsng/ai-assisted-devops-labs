# Task Manager — AI-Assisted DevOps Lab

A self-paced lab where you build a production-quality three-tier web application using **Claude Code at every step** of the delivery lifecycle: design → code → test → document → secure → review → ship.

**Stack:** React 18 + TypeScript · FastAPI (Python 3.12) · PostgreSQL 16 · Docker Compose · GitHub Actions

---

## Quick Start

```bash
# Prerequisites: Git, Docker Desktop, Node 20+, Python 3.12+, Claude Code CLI
npm install -g @anthropic-ai/claude-code

cp .env.example .env
# Edit .env — set SECRET_KEY to: python3 -c "import secrets; print(secrets.token_hex(32))"

docker compose up
```

### Core services

| Service | URL | Purpose |
|---------|-----|---------|
| Frontend | http://localhost:5173 | React UI |
| API | http://localhost:8000 | FastAPI service |
| API Docs | http://localhost:8000/docs | Swagger UI |
| Database | localhost:5432 | PostgreSQL |

### Observability stack (optional — requires Docker)

```bash
docker compose --profile observability up
```

| Service | URL | Purpose |
|---------|-----|---------|
| Jaeger | http://localhost:16686 | Distributed trace UI |
| Prometheus | http://localhost:9090 | Metrics query and alerting |
| Grafana | http://localhost:3000 | Unified dashboards (admin/admin) |

---

## Running Tests

```bash
# Backend — unit + integration tests with coverage
cd backend && pip install -e ".[dev]" aiosqlite
pytest --cov=app --cov-report=term-missing

# Frontend — component tests with coverage
cd frontend && npm ci && npm test

# E2E — full browser tests (requires running stack)
cd frontend && npm run e2e
```

CI enforces ≥70% coverage on both backend and frontend. The `security` CI job also runs bandit SAST, pip-audit, and npm audit on every push.

---

## Claude Code Skills

These project skills are available as soon as you open Claude Code in this directory. Type `/skill-name` to run any of them.

### Coding Standards

| Skill | What it does |
|-------|-------------|
| `/check-python` | Run black/isort/ruff — read-only report with explanations |
| `/fix-python [file]` | Auto-apply black, isort, ruff --fix |
| `/check-frontend` | Run tsc + ESLint — read-only report with explanations |
| `/fix-frontend [file]` | Auto-apply ESLint --fix; explain remaining manual fixes |
| `/check-standards` | Full pre-merge gate: all linters + both test suites + Docker build |
| `/review-conventions` | AI review: layer boundaries, naming, git hygiene |
| `/check-db` | Review SQLAlchemy models, Alembic migrations, repository patterns |

### Security

| Skill | What it does |
|-------|-------------|
| `/security-scan` | Automated scan: bandit SAST + pip-audit + npm audit + secret patterns |
| `/security-review` | AI OWASP Top 10 review mapped to this codebase |
| `/check-secrets` | Detect hardcoded credentials in tracked files and git history |
| `/check-dependencies` | CVE audit for Python + JS packages; checks lock file hygiene |
| `/threat-model [feature]` | STRIDE threat model — produces a prioritised mitigation backlog |

**Shift-left tip:** Run `/check-secrets` before your first commit, `/security-scan` after implementing auth (Module 5), and `/threat-model` when designing a new feature.

### Performance & Security Testing

| Skill | What it does |
|-------|-------------|
| `/load-test [smoke\|load\|spike\|locust]` | Run a k6 or Locust scenario, parse results, correlate with Prometheus + Jaeger |
| `/pen-test [authentication\|access-control\|injection\|design]` | Structured pen test — automated checks + ZAP scan + OWASP findings report |

---

## Lab Modules

Work through the modules in order. Each has learning objectives, step-by-step instructions, and a checkpoint.

| Module | Topic |
|--------|-------|
| [00](docs/modules/00-setup.md) | Environment Setup & Claude Code Orientation |
| [01](docs/modules/01-architecture.md) | Architecture Design with Claude Code |
| [02](docs/modules/02-api-design.md) | API Design (OpenAPI First) |
| [03](docs/modules/03-git-workflow.md) | Git Workflow & Project Scaffolding |
| [04](docs/modules/04-database.md) | Database Tier (PostgreSQL + SQLAlchemy) |
| [05](docs/modules/05-business-logic.md) | Business Logic Tier (FastAPI) |
| [05b](docs/modules/05b-observability.md) | Observability (Logs · Metrics · Traces — OTel + Prometheus + Jaeger + Grafana) |
| [06](docs/modules/06-frontend.md) | Frontend Tier (React + TypeScript) |
| [07](docs/modules/07-testing.md) | Testing (Unit, Integration, Component) |
| [07b](docs/modules/07b-e2e-testing.md) | E2E Testing with Playwright |
| [08](docs/modules/08-documentation.md) | Documentation |
| [09](docs/modules/09-cicd.md) | CI/CD with GitHub Actions |
| [10](docs/modules/10-review-and-reflection.md) | Code Review & Reflection |
| [11](docs/modules/11-load-testing.md) | Load Testing (Locust + k6 + Grafana correlation) |
| [12](docs/modules/12-pen-testing.md) | Penetration Testing (OWASP ZAP + manual checks) |
| [13](docs/modules/13-continuous-deployment.md) | Continuous Deployment (GHCR image publishing + Fly.io + Alembic migrations) |

---

## Project Structure

```
task-manager/
├── .claude/
│   └── commands/           # Project skills (type /skill-name in Claude Code)
│       ├── check-python.md      check-frontend.md    check-standards.md
│       ├── fix-python.md        fix-frontend.md      review-conventions.md
│       ├── check-db.md          security-scan.md     security-review.md
│       ├── check-secrets.md     check-dependencies.md  threat-model.md
│       └── load-test.md         pen-test.md
├── .github/
│   ├── workflows/ci.yml        # 5 parallel jobs: backend · frontend · security · docker-build · smoke-test
│   ├── workflows/publish.yml   # CD pipeline: build images → GHCR → Fly.io deploy → health check
│   ├── pull_request_template.md
│   └── ISSUE_TEMPLATE/
├── backend/
│   ├── app/
│   │   ├── models/         # SQLAlchemy ORM models (Mapped[] annotations)
│   │   ├── routers/        # FastAPI route handlers (HTTP in/out only)
│   │   ├── schemas/        # Pydantic request/response models
│   │   ├── services/       # Business logic (status transitions, auth rules)
│   │   ├── repositories/   # Database access layer (SQL only, no business logic)
│   │   ├── middleware/     # RequestLoggingMiddleware, MetricsMiddleware
│   │   └── telemetry.py    # OpenTelemetry setup (traces → Jaeger, metrics → Prometheus)
│   └── tests/
├── frontend/
│   └── src/
│       ├── api/            # Typed API client + OpenAPI-generated types
│       ├── components/     # Reusable UI components
│       └── pages/          # Page-level components
├── observability/
│   ├── prometheus.yml      # Scrape config: api:8000/metrics every 15 s
│   └── grafana/
│       ├── provisioning/   # Auto-provisioned Prometheus + Jaeger data sources
│       └── dashboards/     # Pre-built Task Manager API dashboard
├── docs/
│   ├── adr/                # Architecture Decision Records
│   ├── api/openapi.yaml    # OpenAPI 3.1 spec (source of truth for all endpoints)
│   ├── diagrams.md         # UML diagrams in Mermaid (architecture, ER, sequence, class)
│   ├── modules/            # Lab module guides (one file per module)
│   └── reflection.md       # Student reflection template
├── load-tests/
│   ├── locustfile.py       # Locust scenarios: ReadHeavy (6), TaskWriter (3), AuthStress (1)
│   └── k6/
│       ├── smoke.js        # 1 VU, 60 s — verify full user journey before any load
│       ├── load.js         # Ramp to 50 VUs — SLO gates: P95 < 500 ms, errors < 1%
│       └── spike.js        # Burst to 200 VUs — verify recovery after spike
├── pen-tests/
│   ├── manual-checks.sh    # Automated OWASP A01–A07 curl checks (PASS/FAIL report)
│   ├── zap-scan.sh         # Docker-based ZAP baseline and full active scan
│   └── reports/            # ZAP HTML + JSON reports land here (gitignored)
├── .pre-commit-config.yaml # Hooks: detect-secrets, bandit, black, isort, ruff
├── CLAUDE.md               # Project context for Claude Code
├── CONTRIBUTING.md         # Branch strategy, commit conventions, PR process
└── docker-compose.yml
```

---

## UML Diagrams

See [`docs/diagrams.md`](docs/diagrams.md) for all architecture diagrams in Mermaid:
- **Architecture** — three tiers, observability stack, ports, CI/CD pipeline
- **Use Case** — what Guest and Authenticated User can do
- **Sequence** — status transition (happy path), 422 error flow, login flow
- **Class** — domain models, services, repositories, telemetry
- **ER** — full PostgreSQL schema with columns, types, and foreign keys

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch strategy, commit conventions, pre-commit hook setup, and the PR process (including the security checklist).

---

## Assessment

| Criterion | Weight |
|-----------|--------|
| Working app (all tiers run via `docker compose up`) | 30% |
| GitHub repo quality (commits, branch strategy, PR template) | 20% |
| Test coverage ≥ 70% (CI-enforced on both backend and frontend) | 20% |
| Peer code review (substantive feedback given and received) | 15% |
| Reflection report (`docs/reflection.md`, 400–600 words) | 15% |
