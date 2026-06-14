# Solution — AI-Assisted DevOps Lab

This folder contains the **reference solution** for all 13 modules of the Task Manager lab. It represents what a student should produce by the end of the lab.

## How to use this folder

### As a student
- Complete each module first using only the lab guides in `docs/modules/`
- Use this folder to check your work or unblock yourself when stuck
- Pay attention to the ADRs and reflection — these are the parts that require the most original thought

### As an instructor
- Run `docker compose up` from this directory to verify the solution works end-to-end
- Use the pen test report and reflection as calibration samples for grading

## What's here vs the starter scaffold

| Item | Status |
|------|--------|
| Backend app (FastAPI) | Complete — all routers, services, repositories, models |
| Frontend (React) | Complete — all pages, components, API client |
| Tests | Complete — unit + integration + component (≥70% coverage) |
| Alembic migrations | Added — `alembic/versions/001_initial_schema.py` |
| Production Dockerfiles | Added — multi-stage builds for API and frontend |
| CI workflow | Identical to scaffold `ci.yml` |
| CD workflow (publish.yml) | Identical to scaffold `publish.yml` |
| fly.toml | Added — Fly.io deployment config |
| ADRs | Added — 3 ADRs documenting key decisions |
| Pen test report | Added — `docs/pen-test-report.md` |
| Reflection | Added — `docs/reflection.md` (example) |

## Running the solution

```bash
cd solution
cp .env.example .env
# Set SECRET_KEY: python3 -c "import secrets; print(secrets.token_hex(32))"

docker compose up
```

API: http://localhost:8000  
Docs: http://localhost:8000/docs  
Frontend: http://localhost:5173

## Running tests

```bash
cd solution/backend
pip install -e ".[dev]"
pytest --cov=app --cov-report=term-missing
```
