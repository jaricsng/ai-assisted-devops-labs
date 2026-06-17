Review the GCP Cloud Run deployment configuration (`infra/gcp/`, `infra/gcp/deploy.sh`, and the `deploy-gcp` job in `.github/workflows/publish.yml`) against GCP best practices for security, reliability, and cost efficiency. If `$ARGUMENTS` is provided, review that specific file.

---

## 1. Cloud Run Service YAMLs (`infra/gcp/api-service.yaml`, `infra/gcp/frontend-service.yaml`)

Read both files.

### 1a. Service account (least privilege)
- Every Cloud Run service must have an explicit `serviceAccountName` that is a **dedicated service account** (not the default Compute Engine service account `PROJECT_ID-compute@developer.gserviceaccount.com` which has broad Editor/Owner-level access by default).
- The API service account should have only:
  - `roles/cloudsql.client` (connect to Cloud SQL)
  - `roles/secretmanager.secretAccessor` for the specific secrets (`task-manager-database-url`, `task-manager-secret-key`)
  - `roles/cloudtrace.agent` and `roles/monitoring.metricWriter` (if OTel is enabled)
- The frontend service account needs no GCP permissions (it serves static assets + proxies to API).
- Flag if `serviceAccountName` is absent or points to the default compute SA.

### 1b. Secrets — Secret Manager, not env var plaintext
- Sensitive values (`DATABASE_URL`, `SECRET_KEY`) must appear in the `env[].valueFrom.secretKeyRef` pattern, **not** in `env[].value` as plaintext strings.
- Run:

```bash
python3 -c "
import yaml, sys
for f in ['infra/gcp/api-service.yaml', 'infra/gcp/frontend-service.yaml']:
    d = yaml.safe_load(open(f))
    containers = d['spec']['template']['spec']['containers']
    for c in containers:
        for e in c.get('env', []):
            if 'value' in e and any(k in e['name'].upper() for k in ['KEY','SECRET','PASSWORD','TOKEN','URL']):
                print(f'POSSIBLE PLAINTEXT SECRET in {f}: {e[\"name\"]}')
"
```

- Verify secret names in `secretKeyRef.name` (`task-manager-database-url`, `task-manager-secret-key`) match the Secret Manager secret IDs exactly — a mismatch causes deployment failure with a cryptic permission error.

### 1c. Cloud SQL connection
- The API service connects to Cloud SQL. Verify:
  - `run.googleapis.com/cloudsql-instances` annotation is set with the full connection name (`PROJECT_ID:REGION:INSTANCE_NAME`) — this enables the Cloud SQL Auth Proxy sidecar automatically.
  - `DATABASE_URL` uses the Unix socket path (`/cloudsql/...`) for Cloud SQL via the proxy, **not** a direct TCP connection (`@IP:5432`). Direct TCP bypasses the proxy's mTLS and requires a public IP on the Cloud SQL instance.
- Recommended URL format via Cloud SQL proxy (Unix socket): `postgresql+asyncpg://user:pass@/dbname?host=/cloudsql/PROJECT_ID:REGION:INSTANCE_NAME`
- Flag if the `DATABASE_URL` contains a numeric IP or hostname without the socket path.

### 1d. Ingress settings
- `run.googleapis.com/ingress: all` — allows public internet access. Use `internal-and-cloud-load-balancing` if the API should only be accessible through a GCP Load Balancer (recommended for production — gives you Cloud Armor WAF).
- For the frontend, `all` ingress is appropriate (it serves the public).
- For the API, consider `internal-and-cloud-load-balancing` with a GCP HTTPS Load Balancer in front.

### 1e. Scaling
- `autoscaling.knative.dev/minScale: "1"` prevents cold starts — verify this is set for the API (FastAPI with OTel has a slow cold start).
- `autoscaling.knative.dev/maxScale` must be set — an unbounded service can scale to hundreds of instances under a traffic spike, generating unexpected bills and overwhelming the database connection pool.
- `run.googleapis.com/cpu-throttling: "false"` — only set this if the app needs CPU outside of request handling (e.g., background tasks). For a standard FastAPI app, keep CPU throttling enabled (default) to reduce cost.

### 1f. Resource limits
- `resources.limits.cpu` and `resources.limits.memory` must be set explicitly. Defaults are 1 CPU and 512Mi — too small for FastAPI + OTel + asyncpg. Recommended: 1 CPU / 512Mi for the API, 256Mi for the frontend.
- Cloud Run charges for CPU + memory during request processing — oversizing increases cost proportionally.

### 1g. Health probes
- `livenessProbe` (port 8000, path `/health`) must be defined for the API — Cloud Run uses it to restart unhealthy instances.
- `readinessProbe` (path `/ready`) should also be defined — it checks DB connectivity and prevents traffic from reaching the instance before the connection pool is warmed up.

```bash
grep -n "health\|ready" backend/app/main.py | head -10
```

---

## 2. Deploy Script (`infra/gcp/deploy.sh`)

Read `infra/gcp/deploy.sh`.

**Check:**
- `set -euo pipefail` is present — flag if missing.
- All required variables (`PROJECT_ID`, `REGION`, `GITHUB_USERNAME`) are validated with `:?` syntax.
- The script uses `gcloud run services replace` (declarative, idempotent) rather than `gcloud run deploy` (imperative) — declarative is preferred because it applies the full YAML and is reproducible.
- The API URL is extracted from `gcloud run services describe ... --format="value(status.url)"` and passed to the frontend deployment — **not hardcoded**. A hardcoded URL in `frontend-service.yaml` will be wrong in new environments.
- IAM binding `--member="allUsers"` makes the service public. In production, use IAM Invoker bindings only for the Load Balancer service account, not `allUsers`, and put Cloud Armor in front.
- Flag the `allUsers` IAM binding as ⚠️ advisory for production (acceptable for a lab/demo).

---

## 3. CI/CD Pipeline (`publish.yml` — `deploy-gcp` job)

Read `.github/workflows/publish.yml`, focus on the `deploy-gcp` job.

**Check:**
- The job uses `google-github-actions/auth@v2` with **Workload Identity Federation** (`workload_identity_provider` + `service_account`) — **not** a service account JSON key (`credentials_json`). A JSON key is a long-lived credential that cannot be rotated automatically and is a common leak vector.
- Flag if `credentials_json: ${{ secrets.GCP_SA_KEY }}` is used — this is the legacy approach. Migrate to WIF.
- The job is gated by the `production-gcp` GitHub Environment — flag if environment is missing.
- `gcloud auth configure-docker` is not needed if using GHCR (not GCR/Artifact Registry). Flag if it's present but the images still come from `ghcr.io` (unnecessary step that adds a permission footprint).

---

## 4. Container Registry: Artifact Registry vs GHCR

**Check (advisory):**
- Images are pulled from `ghcr.io` (external). For GCP production:
  - Cloud Run in a private VPC cannot pull from `ghcr.io` without Cloud NAT configured (egress cost + latency).
  - **Google Artifact Registry** (`REGION-docker.pkg.dev/PROJECT_ID/...`) stores images within GCP network (no egress cost, faster pulls, integrated vulnerability scanning via Artifact Analysis).
- Flag if deploying to a VPC-connected Cloud Run service while referencing `ghcr.io` images — add Cloud NAT or migrate to Artifact Registry.

---

## 5. Database: Cloud SQL vs Container

**Check:**
- `DATABASE_URL` must point to **Cloud SQL for PostgreSQL** (managed), not a PostgreSQL container running in Cloud Run. Cloud Run containers are stateless — any data in a PostgreSQL container is lost when the container is replaced.
- If the `DATABASE_URL` secret in Secret Manager resolves to `@localhost:5432` or a container hostname, flag it as ❌ critical.

---

## 6. Observability

**Check `infra/gcp/api-service.yaml`:**
- If `OTEL_ENABLED=true`, `OTLP_ENDPOINT` (or `OTEL_EXPORTER_OTLP_ENDPOINT`) must point to **Google Cloud's OTLP endpoint** or a self-hosted OpenTelemetry Collector (e.g., `https://telemetry.googleapis.com:443`) — not to `jaeger:4317` (the local dev endpoint).
- Cloud Trace and Cloud Monitoring are the native GCP observability backends. Alternatively, a hosted Grafana on GCP works with the existing Prometheus/Jaeger setup.
- GCP Cloud Run automatically emits request logs to Cloud Logging — verify `OTEL_LOGS_EXPORTER` is not set to a non-GCP endpoint that would duplicate logs.

---

## 7. Frontend: `VITE_API_URL` with Dynamic API URL

**Check `infra/gcp/frontend-service.yaml`:**
- `VITE_API_URL` contains a hardcoded Cloud Run URL (`https://task-manager-api-HASH-REGION.a.run.app`). This URL changes every time the API service is deployed to a new region or project.
- The deploy script should dynamically resolve the API URL and pass it as a build arg or env var — verify `deploy.sh` substitutes this value before deploying the frontend.
- For production, set a **custom domain** via Cloud Run domain mappings and reference the stable custom domain in `VITE_API_URL` — never reference the auto-generated `*.run.app` URL in production.

---

## Output Format

```
── infra/gcp/api-service.yaml ──────────────────────
✅ serviceAccountName set (task-manager-api@...)
✅ minScale: 1 (no cold starts)
✅ healthCheck: /health liveness probe configured
❌ DATABASE_URL in env[].value as plaintext — use valueFrom.secretKeyRef
⚠️  cpu-throttling: false — remove unless app has background tasks (unnecessary cost)
⚠️  ingress: all — consider internal-and-cloud-load-balancing + Cloud Armor for production

── infra/gcp/deploy.sh ─────────────────────────────
✅ set -euo pipefail present
✅ API URL dynamically extracted and passed to frontend deploy
⚠️  allUsers IAM binding — acceptable for lab, use load balancer SA for production

── CI/CD (deploy-gcp) ───────────────────────────────
❌ Uses credentials_json (SA JSON key) — migrate to Workload Identity Federation
✅ Gated by production-gcp GitHub Environment
```

Final summary:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  GCP Deployment Review — Task Manager
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Service account (least privilege)  ✅ / ⚠️ / ❌
  Secrets (Secret Manager)           ✅ / ⚠️ / ❌
  Cloud SQL connection (proxy/socket) ✅ / ⚠️ / ❌
  Ingress & WAF                      ✅ / ⚠️ / ❌
  Scaling (min/max replicas)         ✅ / ⚠️ / ❌
  Health probes                      ✅ / ⚠️ / ❌
  Deploy script                      ✅ / ⚠️ / ❌
  CI/CD (WIF vs JSON key)            ✅ / ⚠️ / ❌
  Container registry (AR vs GHCR)    ✅ / ⚠️ / ❌
  Database (Cloud SQL vs container)  ✅ / ⚠️ / ❌
  Observability (Cloud Trace)        ✅ / ⚠️ / ❌
  Frontend dynamic URL               ✅ / ⚠️ / ❌

  ❌ Must fix before production:  N
  ⚠️  Should fix:                N
  ✅ Passed:                     N
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

For every ❌: quote the problematic config, explain the specific risk (data loss, credential leak, billing surprise, deployment failure), and provide the corrected YAML or script snippet.
