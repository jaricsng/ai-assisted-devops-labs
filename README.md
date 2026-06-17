# Task Manager — AI-Assisted DevOps Lab

A self-paced lab where you build a production-quality three-tier web application using **Claude Code at every step** of the delivery lifecycle: design → code → test → document → secure → review → ship → operate.

**Stack:** React 18 + TypeScript · FastAPI (Python 3.12) · PostgreSQL 16 · Docker Compose · .NET Aspire · GitHub Actions · bcrypt · JWT + JTI revocation · structlog + OpenTelemetry (traces → Jaeger · metrics → Prometheus) · Dependabot

---

## Quick Start

### Option A — .NET Aspire (preferred for local dev)

```bash
# One-time setup
dotnet workload install aspire

cp .env.example .env
dotnet run --project aspire/TaskManager.AppHost
# Aspire Dashboard → https://localhost:15888  (traces, logs, health)
```

### Option B — Docker Compose

```bash
# Prerequisites: Git, Docker Desktop, Node 20+, Python 3.12+, Claude Code CLI
npm install -g @anthropic-ai/claude-code

cp .env.example .env
# Edit .env — set SECRET_KEY to: python3 -c "import secrets; print(secrets.token_hex(32))"

docker compose up

# Optional: load demo account + sample data
docker compose exec api python seed.py
```

### Demo account (after running seed.py)

| Field | Value |
|-------|-------|
| Email | `demo@example.com` |
| Password | `Demo1234!` |

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
| Prometheus | http://localhost:9090 | Metrics scraping and alerting |
| Grafana | http://localhost:3000 | Unified dashboards (admin/admin) |
| Blackbox Exporter | http://localhost:9115 | External endpoint prober (powers `DatabaseUnreachable` alert) |

---

## Running Tests

### Backend — unit + integration tests

The backend requires Python 3.12. Use Docker to guarantee the right version regardless of your system Python:

```bash
# Recommended — Docker runner (guarantees Python 3.12; requires `docker compose up -d` for the DB)
docker run --rm \
  --network task-manager_default \
  -e DATABASE_URL="postgresql+asyncpg://taskuser:taskpass@db:5432/taskmanager" \
  -e SECRET_KEY="test-secret-key-for-local-dev-only" \
  -e ENVIRONMENT=test \
  -e OTEL_ENABLED=false \
  -v "$(pwd)/backend:/app" \
  -w /app \
  python:3.12-slim \
  bash -c "pip install -e '.[dev]' -q && pytest tests/ --cov=app --cov-report=term-missing -v"

# Alternative — if your system already runs Python 3.12
cd backend && pip install -e ".[dev]"
ENVIRONMENT=test pytest --cov=app --cov-report=term-missing
# ENVIRONMENT=test switches the DB engine to NullPool for asyncpg task-boundary safety
```

### Frontend — component tests

```bash
cd frontend && npm ci && npm test
```

### E2E — browser tests (requires running stack)

```bash
cd frontend && npm run e2e
```

> **Rate-limiter note:** The pen test fires 20 rapid login attempts, exhausting the in-memory per-IP sliding-window rate limiter. If you run the pen test before E2E tests, run `docker compose restart api` first to reset rate limit state.

### Load tests — k6 (requires `docker compose up -d`)

```bash
# Smoke — 1 VU, 60 s; verifies the full user journey before any load run
k6 run load-tests/k6/smoke.js

# Load — ramps to 50 VUs, holds 5 min; SLO gates: p95 < 500 ms, errors < 1%
k6 run load-tests/k6/load.js

# Spike — bursts to 100 VUs; verifies recovery after a sudden traffic event
k6 run load-tests/k6/spike.js

# No local k6 install? Use Docker (requires `docker compose up -d`):
docker run --rm --network task-manager_default \
  -e BASE_URL=http://api:8000 \
  -v "$(pwd)/load-tests/k6:/scripts" \
  grafana/k6 run /scripts/smoke.js
```

Or use the Claude Code skill: `/load-test [smoke|load|spike]`

### Load tests — Locust (web UI)

```bash
pip install locust
locust -f load-tests/locustfile.py --host http://localhost:8000
# Open http://localhost:8089, set users and spawn rate, click Start
```

### Pen test (requires `docker compose up -d`)

```bash
# Automated OWASP checks A01–A07 + enterprise governance (Module 14)
chmod +x pen-tests/manual-checks.sh
./pen-tests/manual-checks.sh http://localhost:8000

# OWASP ZAP baseline scan — passive analysis + light active scan (Docker, no install needed)
chmod +x pen-tests/zap-scan.sh
./pen-tests/zap-scan.sh http://localhost:8000
# HTML + JSON reports land in pen-tests/reports/
open pen-tests/reports/zap-report-*.html   # macOS
```

Or use the Claude Code skill: `/pen-test [authentication|access-control|injection|design]`

---

CI enforces ≥70% coverage on both backend and frontend. The `security` CI job runs bandit SAST (hard gate — non-zero exit on any medium+ finding), pip-audit, and npm audit on every push. Dependabot opens weekly PRs for pip, npm, and GitHub Actions updates.

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

### Compliance

| Skill | What it does |
|-------|-------------|
| `/compliance-check [domain]` | Full best-practice compliance gate across 12 domains: code quality, security SAST, dependency CVEs, security runtime, architecture conventions, database patterns, governance headers, observability, documentation, container security, and CI/CD. Pass a domain name to scope to one area; no arg runs all 12 and produces a scorecard. |

### Performance & Security Testing

| Skill | What it does |
|-------|-------------|
| `/load-test [smoke\|load\|spike\|locust]` | Run a k6 or Locust scenario, parse results, correlate with Prometheus + Jaeger |
| `/pen-test [authentication\|access-control\|injection\|design]` | Structured pen test — automated checks + ZAP scan + OWASP findings report |

### Deployment & Cloud

| Skill | What it does |
|-------|-------------|
| `/check-aspire [file]` | Review Aspire AppHost wiring, secret hygiene, manifest readiness |
| `/check-azure [file]` | Review Azure Container Apps config, OIDC auth, Key Vault, scaling |
| `/check-aws [file]` | Review ECS Fargate task defs, IAM least-privilege, Secrets Manager, OIDC |
| `/check-gcp [file]` | Review Cloud Run YAMLs, Workload Identity, Secret Manager, Cloud SQL proxy |

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
| [13](docs/modules/13-continuous-deployment.md) | Continuous Deployment (GHCR · Trivy scan · SBOM · multi-cloud deploy: Fly.io / AWS ECS / GCP Cloud Run / Azure Container Apps) |
| [14](docs/modules/14-enterprise-governance.md) | Enterprise Governance & Compliance (security headers · audit logging · token revocation · GDPR · supply chain) |
| [15](docs/modules/15-slos-and-error-budgets.md) | SLIs, SLOs & Error Budgets (recording rules · burn-rate alerts · Grafana SLO dashboard · runbooks · incident simulation) |
| [16](docs/modules/16-multi-environment.md) | Multi-Environment Strategy & Promotion Pipeline (staging → production · GitHub Environments · expand/contract migrations · blue-green) |
| [17](docs/modules/17-infrastructure-as-code.md) | Infrastructure as Code — Terraform (remote state · reusable modules · plan-in-CI · apply-in-CD · drift detection) |
| [18](docs/modules/18-incident-response.md) | Incident Response & On-Call Engineering (severity classification · runbooks · blameless post-mortems · alert landscape mapping) |
| [19](docs/modules/19-threat-modeling.md) | Threat Modeling & Security Architecture (STRIDE · Data Flow Diagrams · threat register · mitigation verification · accepted risk documentation) |

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
│       ├── load-test.md         pen-test.md          compliance-check.md
│       └── check-aspire.md      check-azure.md       check-aws.md       check-gcp.md
├── .github/
│   ├── workflows/ci.yml        # 7 jobs: backend · frontend · security (hard gate) · docker-build · smoke-test · e2e · terraform-plan+tfsec (PRs only)
│   ├── workflows/publish.yml   # CD pipeline: build → GHCR → Trivy scan → SBOM → cosign verify → deploy (Fly.io/AWS/GCP/Azure, each gated by if:false) → ZAP baseline scan
│   ├── dependabot.yml          # Weekly dependency updates: pip · npm · github-actions
│   ├── pull_request_template.md
│   └── ISSUE_TEMPLATE/
├── backend/
│   ├── app/
│   │   ├── models/         # SQLAlchemy ORM models (Mapped[] annotations)
│   │   ├── routers/        # FastAPI route handlers (HTTP in/out only)
│   │   ├── schemas/        # Pydantic request/response models
│   │   ├── services/       # Business logic (status transitions, auth rules)
│   │   ├── repositories/   # Database access layer (SQL only, no business logic)
│   │   ├── middleware/     # SecurityHeadersMiddleware, MaxBodySizeMiddleware, RateLimitMiddleware, RequestLoggingMiddleware, MetricsMiddleware
│   │   └── telemetry.py    # OpenTelemetry setup (traces → Jaeger, metrics → Prometheus)
│   └── tests/
├── frontend/
│   └── src/
│       ├── api/            # Typed API client + OpenAPI-generated types
│       ├── components/     # Reusable UI components
│       └── pages/          # Page-level components
├── observability/
│   ├── prometheus.yml      # Scrape config: api:8000/metrics + blackbox readiness probe
│   ├── blackbox.yml        # Blackbox Exporter config (http_2xx module)
│   └── grafana/
│       ├── provisioning/
│       │   ├── datasources/   # Auto-provisioned Prometheus + Jaeger data sources
│       │   └── alerting/
│       │       └── rules.yaml # 4 Grafana alert rules (HighErrorRate, HighLatency, DatabaseUnreachable, HighRejectionRate)
│       └── dashboards/     # Pre-built Task Manager API dashboard
├── docs/
│   ├── adr/                # 7 Architecture Decision Records (architecture · API design · security · soft-delete · deployment · observability · rate limiting)
│   ├── api/openapi.yaml    # OpenAPI 3.1 spec (source of truth for all endpoints)
│   ├── modules/            # Lab module guides (one file per module, 00–19 + 05b + 07b)
│   ├── diagrams.md         # UML diagrams in Mermaid (architecture, use case, sequence, class, ER)
│   ├── user-guide.md       # End-user guide: projects, tasks, Kanban board, observability, API access
│   ├── operations.md       # Ops reference: start/stop, logs, DB access, health checks, troubleshooting
│   ├── rubric.md           # Assessment rubric with 4-level performance descriptors
│   ├── instructor-guide.md # Instructor delivery guide and facilitation notes
│   ├── pen-test-report.md  # Sample pen test findings report (students produce their own)
│   └── reflection.md       # Student reflection template
├── load-tests/
│   ├── locustfile.py       # Locust scenarios: ReadHeavy (6), TaskWriter (3), AuthStress (1)
│   └── k6/
│       ├── smoke.js        # 1 VU, 60 s — verify full user journey before any load
│       ├── load.js         # Ramp to 50 VUs — SLO gates: P95 < 500 ms, errors < 1%
│       └── spike.js        # Burst to 100 VUs — verify recovery after spike
├── pen-tests/
│   ├── manual-checks.sh    # Automated OWASP A01–A07 + Module 14 governance checks (PASS/FAIL)
│   ├── zap-scan.sh         # Docker-based ZAP baseline and full active scan
│   └── reports/            # ZAP HTML + JSON reports land here (gitignored)
├── aspire/
│   ├── TaskManager.AppHost/       # .NET Aspire orchestration (preferred for local dev)
│   └── TaskManager.ServiceDefaults/  # Shared OTel + health defaults
├── aws/
│   └── ecs/                # ECS Fargate task definitions
├── infra/
│   └── gcp/                # Cloud Run service manifests
├── azure.yaml              # Azure Developer CLI config (azd up)
├── solution/               # Reference implementation — consult when stuck
├── .pre-commit-config.yaml # Hooks: detect-secrets, bandit, black, isort, ruff
├── CLAUDE.md               # Project context for Claude Code (19 custom skills)
├── CODE_OF_CONDUCT.md      # Contributor Covenant v2.1
├── CONTRIBUTING.md         # Branch strategy, commit conventions, PR process
├── SECURITY.md             # Vulnerability reporting policy and response SLAs
└── docker-compose.yml
```

---

## UML Diagrams

See [`docs/diagrams.md`](docs/diagrams.md) for all architecture diagrams in Mermaid:
- **Architecture** — three tiers, observability stack, ports, CI/CD pipeline
- **Use Case** — what Guest and Authenticated User can do
- **Sequence** — status transition (happy path), 422 error flow, login flow, logout+revocation, GDPR deletion, rate-limited login (429), observability instrumentation flow
- **Class** — domain models, services, repositories (with soft-delete methods noted)
- **ER** — full PostgreSQL schema with columns, types, foreign keys, and `deleted_at` soft-delete fields

---

## Using the Application

See [docs/user-guide.md](docs/user-guide.md) for the end-user guide: account creation, logging in, managing projects and tasks, the Kanban board workflow, status transitions, and direct API access via Swagger UI.

## Operations

See [docs/operations.md](docs/operations.md) for the full operations reference: start/stop/restart, individual service control, log tailing, database access, health checks, observability stack, and common troubleshooting steps.

---

## Releases

This project uses tagged releases. To check out a specific release:

```bash
git fetch --tags
git checkout v1.0.0              # detached HEAD at that release
# or, to keep working from it:
git checkout -b release/v1.0.0 v1.0.0
```

List all available tags: `git tag -l -n`. See [CHANGELOG.md](CHANGELOG.md) for what changed in each release.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch strategy, commit conventions, pre-commit hook setup, and the PR process (including the security checklist).

---

## Assessment

See [`docs/rubric.md`](docs/rubric.md) for the full grading rubric with 4-level performance descriptors.

| Criterion | Weight |
|-----------|--------|
| Functional application (all tiers run; business logic enforced server-side) | 20% |
| Code quality & architecture (layer boundaries, type safety, conventions) | 15% |
| Testing (≥70% coverage on both tiers; meaningful negative-case tests) | 15% |
| CI/CD pipeline (all jobs pass; GHCR publish; Trivy image scan; SBOM; cloud deploy with health check) | 15% |
| Security practices (OWASP checks pass; security headers; token revocation; GDPR deletion; no secrets in git; pen test report) | 10% |
| DevOps practices (git workflow, observability, load testing, ADRs) | 10% |
| Documentation (README, OpenAPI spec, docstrings, ADRs) | 5% |
| Peer collaboration & code review (substantive feedback given and received) | 5% |
| Reflection on AI-assisted development (`docs/reflection.md`) | 5% |
