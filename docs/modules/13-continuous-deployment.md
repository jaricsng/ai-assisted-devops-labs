# Module 13 — Continuous Deployment

## Learning Objectives

- Understand the difference between Continuous Integration, Continuous Delivery, and Continuous Deployment
- Build production-grade multi-stage Docker images for the API and frontend
- Publish versioned Docker images to GitHub Container Registry (GHCR)
- Deploy the Task Manager to Fly.io from a GitHub Actions workflow
- Manage production secrets safely using platform secret stores
- Run Alembic database migrations as a step inside the deployment pipeline
- Verify a deployment with a post-deploy health check and smoke test
- Implement a one-command rollback for failed deployments

---

## Background: CI vs CD

| Term | Meaning | When it runs |
|------|---------|-------------|
| **CI** (Continuous Integration) | Every push triggers automated quality gates (lint, test, security, build) | On every push and PR |
| **Continuous Delivery** | Every passing `main` merge produces a deployment-ready artifact; a human approves release | Merge to `main` → image published; deploy on human approval |
| **Continuous Deployment** | Every passing `main` merge deploys automatically to production | Merge to `main` → live in production within minutes |

This module implements **Continuous Delivery** by default (you must approve the Fly.io deploy) and shows how to convert it to full Continuous Deployment by removing the manual approval gate.

```
Developer pushes to feature branch
    → CI: lint + test + security + build     (Module 9)
    → PR approved + merged to main
    → CD: build image → publish to GHCR → run migrations → deploy to Fly.io → verify health
```

---

## Tools and Platform

| Tool | Purpose |
|------|---------|
| GitHub Container Registry (GHCR) | Stores versioned Docker images; free for public repos |
| Fly.io | Deployment platform; free tier supports one app + one PostgreSQL DB |
| `flyctl` | Fly.io CLI for local commands and CI |
| `fly.toml` | Declarative app configuration (region, resources, health checks) |
| Alembic | Database migration runner (`alembic upgrade head` as a release command) |

---

## Setup

### 1. Install Fly.io CLI

```bash
brew install flyctl        # macOS
# or: curl -L https://fly.io/install.sh | sh   (Linux)
flyctl version
```

Sign up and log in:
```bash
flyctl auth signup         # or: flyctl auth login if you have an account
```

### 2. Upgrade the Dockerfiles for production

The starter Dockerfiles are development-grade — they install dev dependencies and run the dev server. Production needs:
- **Multi-stage builds** — compile assets in one stage, copy only the output into the final image
- **No dev dependencies** in the production image
- **Non-root user** — don't run as root inside the container
- **Static file serving** — the frontend Dockerfile should produce a static bundle served by nginx

Ask Claude Code:
> "Rewrite `backend/Dockerfile` as a two-stage build. Stage 1 (`builder`): Python 3.12-slim, install only production dependencies (no `[dev]` extras). Stage 2 (`runner`): Python 3.12-slim, copy the installed packages and app code from stage 1, create a non-root user `appuser`, run uvicorn as that user. Expose port 8000."

Then for the frontend:

> "Rewrite `frontend/Dockerfile` as a two-stage build. Stage 1 (`builder`): node:20-alpine, run `npm ci` and `npm run build`. Stage 2 (`runner`): nginx:alpine, copy the Vite build output from `/app/dist` to `/usr/share/nginx/html`, add an `nginx.conf` that handles React Router's client-side routing (all 404s → index.html). Expose port 80."

After rewriting, verify the builds work:
```bash
docker build -t task-manager-api:test backend/
docker build -t task-manager-frontend:test frontend/
docker run --rm -p 8000:8000 -e DATABASE_URL=... -e SECRET_KEY=... task-manager-api:test
```

---

## Activities

### 1. Publish images to GitHub Container Registry

GHCR stores Docker images linked to your GitHub repository. Images are tagged with the git commit SHA so every deployment is traceable.

Create `.github/workflows/publish.yml`:

```yaml
name: Publish

on:
  push:
    branches: [main]   # only publish on merges to main, not on every PR

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  publish-api:
    name: Build and push API image
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write   # required to push to GHCR

    outputs:
      image-tag: ${{ steps.meta.outputs.tags }}

    steps:
      - uses: actions/checkout@v4

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}  # no extra secret needed

      - name: Extract metadata (tags and labels)
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}/api
          tags: |
            type=sha,format=short          # ghcr.io/user/repo/api:sha-abc1234
            type=raw,value=latest,enable=${{ github.ref == 'refs/heads/main' }}

      - name: Build and push API image
        uses: docker/build-push-action@v5
        with:
          context: backend/
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha     # GitHub Actions layer cache
          cache-to: type=gha,mode=max

  publish-frontend:
    name: Build and push frontend image
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    outputs:
      image-tag: ${{ steps.meta.outputs.tags }}

    steps:
      - uses: actions/checkout@v4

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}/frontend
          tags: |
            type=sha,format=short
            type=raw,value=latest,enable=${{ github.ref == 'refs/heads/main' }}

      - name: Build and push frontend image
        uses: docker/build-push-action@v5
        with:
          context: frontend/
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          build-args: |
            VITE_API_URL=${{ vars.VITE_API_URL }}   # set in repo Variables (not Secrets)
```

Push to `main` and verify the images appear in your GitHub repo under **Packages**.

Ask Claude Code:
> "Explain the difference between `secrets.GITHUB_TOKEN` (used above) and a personal access token. Why can we use `GITHUB_TOKEN` to push to GHCR without creating a separate secret?"

### 2. Create the Fly.io app

```bash
# Create the API app (from the backend/ directory)
cd backend
flyctl launch --name task-manager-api --no-deploy

# Create a managed PostgreSQL database on Fly.io
flyctl postgres create --name task-manager-db

# Attach the database to the app (sets DATABASE_URL automatically)
flyctl postgres attach task-manager-db --app task-manager-api
```

Fly.io creates `fly.toml` in the current directory. Open it and verify the key sections:

```toml
# fly.toml — task-manager API
app = "task-manager-api"
primary_region = "sin"   # Singapore — change to your nearest: lax, ord, fra, nrt

[build]
  image = "ghcr.io/YOUR_GITHUB_USERNAME/task-manager/api:latest"

[env]
  PORT = "8000"
  ENVIRONMENT = "production"
  OTEL_ENABLED = "false"   # enable when you want production observability

[deploy]
  release_command = "alembic upgrade head"   # run migrations before traffic switches

[[services]]
  internal_port = 8000
  protocol = "tcp"

  [[services.ports]]
    handlers = ["http"]
    port = 80
    force_https = true

  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443

  [services.concurrency]
    type = "connections"
    hard_limit = 25
    soft_limit = 20

[[services.http_checks]]
  interval = "10s"
  timeout = "5s"
  grace_period = "30s"
  method = "GET"
  path = "/health"
```

Ask Claude Code:
> "What does the `release_command` in fly.toml do? At what point in the deployment does it run relative to traffic switching? Why is it critical that migrations run before traffic switches to the new version?"

### 3. Set production secrets

Production secrets are **never** stored in `fly.toml` or environment variables in the workflow file. They go into Fly.io's secret store, which injects them as environment variables at runtime.

```bash
# Generate a production JWT secret (different from your local .env SECRET_KEY)
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# Set secrets in Fly.io (these are encrypted at rest, not visible in logs)
flyctl secrets set \
  SECRET_KEY="$SECRET_KEY" \
  ENVIRONMENT="production" \
  --app task-manager-api

# Verify which secrets are set (values are masked)
flyctl secrets list --app task-manager-api
```

Ask Claude Code:
> "Why should the production `SECRET_KEY` be different from the one in `.env`? What would happen if an attacker obtained the production `SECRET_KEY`?"

### 4. Create the CD workflow

Add a `deploy` job to `publish.yml` that runs after the images are published:

```yaml
  deploy:
    name: Deploy to Fly.io
    needs: [publish-api, publish-frontend]
    runs-on: ubuntu-latest
    environment: production       # GitHub Environment — requires manual approval

    steps:
      - uses: actions/checkout@v4

      - name: Install flyctl
        uses: superfly/flyctl-actions/setup-flyctl@master

      - name: Deploy API to Fly.io
        run: flyctl deploy --app task-manager-api --image ghcr.io/${{ github.repository }}/api:sha-${{ github.sha }}
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}

      - name: Verify health check
        run: |
          for i in $(seq 1 12); do
            STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://task-manager-api.fly.dev/health)
            echo "Attempt $i: HTTP $STATUS"
            [ "$STATUS" = "200" ] && echo "✅ Health check passed" && exit 0
            sleep 10
          done
          echo "❌ Health check failed after 120 s — rolling back"
          flyctl releases rollback --app task-manager-api
          exit 1
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
```

Add the `FLY_API_TOKEN` as a GitHub repository secret:
```bash
flyctl auth token   # copy the output
# GitHub repo → Settings → Secrets → Actions → New repository secret
# Name: FLY_API_TOKEN  Value: <token from above>
```

Ask Claude Code:
> "What is a GitHub Environment (the `environment: production` key)? How do you configure it to require a named reviewer to approve the deployment before it runs?"

### 5. Configure the GitHub Environment with manual approval

In your GitHub repo:
1. **Settings → Environments → New environment** — name it `production`
2. Enable **Required reviewers** and add yourself
3. Optionally: set a **deployment branch rule** so only `main` can deploy to production

Now the deploy job will pause at a "Review deployments" prompt. One team member must approve before Fly.io receives the deploy command.

This is **Continuous Delivery** — every `main` merge creates a deployment-ready artifact, but a human approves the final release.

To switch to full **Continuous Deployment** (no approval):
- Remove the `environment: production` line from the `deploy` job
- Now every `main` merge deploys automatically within minutes

Ask Claude Code:
> "What are the trade-offs between Continuous Delivery (with a manual approval gate) and Continuous Deployment (fully automatic)? In what situations would you prefer each?"

### 6. Database migrations in the deployment pipeline

The `release_command = "alembic upgrade head"` in `fly.toml` runs migrations before Fly.io shifts traffic to the new version. This ensures:

1. New code never runs against an old schema
2. If the migration fails, the deploy is aborted and traffic stays on the old version

There is one constraint: **migrations must be backward-compatible with the old code** until the old version is no longer running. This is called the **expand/contract pattern**:

| Phase | Migration | Safe? |
|-------|-----------|-------|
| **Expand** | Add a new nullable column | ✅ Old code ignores it |
| **Migrate data** | Backfill the new column | ✅ Old code still works |
| **Contract** | Drop the old column | ⚠️ Only safe after old version is gone |

Ask Claude Code:
> "I need to rename the column `tasks.description` to `tasks.body`. Show me the two-phase expand/contract migration strategy: Phase 1 (safe to deploy now) and Phase 2 (safe only after the old version is gone). Show the Alembic migration files for both phases."

### 7. Rollback a failed deployment

If a deployment breaks production, Fly.io keeps the previous release:

```bash
# List recent releases
flyctl releases list --app task-manager-api

# Roll back to the previous release immediately
flyctl releases rollback --app task-manager-api

# Roll back to a specific version
flyctl releases rollback v12 --app task-manager-api
```

The CD workflow's health check step already calls `flyctl releases rollback` automatically if the health check fails within 120 seconds.

Ask Claude Code:
> "What is the risk of an automatic rollback if a migration has already run? If we deployed v13 with a migration that added a new column, then rolled back to v12, what state is the database in? Is v12 code still compatible with that database state?"

### 8. Run the k6 smoke test against the live deployment

After the health check passes, run the k6 smoke test against the production URL to verify the full user journey:

Add to the `deploy` job in `publish.yml`:

```yaml
      - name: Smoke test against production
        run: |
          docker run --rm grafana/k6 run - \
            -e BASE_URL=https://task-manager-api.fly.dev \
            < load-tests/k6/smoke.js
```

You'll need to update `load-tests/k6/smoke.js` to read the `BASE_URL` from an environment variable instead of hardcoding `http://localhost:8000`:

```javascript
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
```

Ask Claude Code:
> "Update `load-tests/k6/smoke.js` to use `__ENV.BASE_URL` with a fallback to `http://localhost:8000`. Show only the lines that need to change."

If the smoke test fails, the deploy job exits non-zero and GitHub marks the deployment as failed — giving you a clear signal to investigate before any further changes go out.

---

## Deployment Pipeline Summary

```
Merge to main
    │
    ├─ publish-api ──────────────────────┐
    │   build multi-stage Docker image   │
    │   push to GHCR :sha-abc1234        │
    │                                    ├─ deploy (needs both)
    ├─ publish-frontend ─────────────────┘   │
    │   build React → nginx image            │  [manual approval gate]
    │   push to GHCR :sha-abc1234            │
    │                                    flyctl deploy --image :sha-abc1234
    │                                        │
    │                                    release_command: alembic upgrade head
    │                                        │
    │                                    traffic switches to new version
    │                                        │
    │                                    health check loop (10 attempts × 10 s)
    │                                        │
    │                                    k6 smoke test → https://...fly.dev
    │                                        │
    │                                    ✅ deployment complete
    │                                    ❌ auto-rollback if health/smoke fails
```

---

## Environment Strategy

| Environment | Trigger | Approval | Database |
|-------------|---------|----------|---------|
| Local | `docker compose up` | None | Local PostgreSQL |
| CI | Every push | None | SQLite in-memory |
| Production | Merge to `main` | Manual (GitHub Environment) | Fly.io managed PostgreSQL |

This lab uses two environments (local + production). A real team typically adds **staging** — a production-like environment that receives every `main` merge automatically, with production requiring an additional manual promotion.

Ask Claude Code:
> "Design a three-environment pipeline (dev/staging/production) for this project. What would change in the GitHub Actions workflows? What would the database strategy be for staging?"

---

## Checkpoint

- [ ] `backend/Dockerfile` is a two-stage production build with a non-root user
- [ ] `frontend/Dockerfile` is a two-stage build producing an nginx image
- [ ] Both images build successfully with `docker build`
- [ ] `.github/workflows/publish.yml` publishes images to GHCR on merge to `main`
- [ ] Images are visible in your GitHub repo under **Packages**
- [ ] `fly.toml` has `release_command = "alembic upgrade head"`
- [ ] Production `SECRET_KEY` is set via `flyctl secrets set` (not in any file)
- [ ] `FLY_API_TOKEN` is set as a GitHub repository secret
- [ ] `deploy` job runs after `publish-api` and `publish-frontend` and requires approval
- [ ] Post-deploy health check passes; auto-rollback triggers if it fails
- [ ] k6 smoke test runs against the live Fly.io URL
- [ ] Commit: `feat(cd): add production Dockerfiles, GHCR publish, and Fly.io deploy pipeline`

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `flyctl deploy` fails with auth error | `FLY_API_TOKEN` not set or expired | Re-run `flyctl auth token` and update the secret |
| `alembic upgrade head` fails during deploy | Migration depends on a column the old code doesn't have | Use expand/contract — split into two deployments |
| Health check fails after deploy | App crashed at startup | `flyctl logs --app task-manager-api` to see the error |
| GHCR push denied | `packages: write` permission missing | Verify the `permissions:` block in the publish job |
| Frontend shows 404 on page refresh | nginx config missing `try_files` directive | Add `try_files $uri $uri/ /index.html;` to the nginx location block |
| Image not found during deploy | SHA tag doesn't match | Ensure `${{ github.sha }}` matches between publish and deploy jobs |
