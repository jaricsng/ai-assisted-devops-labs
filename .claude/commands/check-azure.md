Review the Azure Container Apps deployment configuration (`azure.yaml`, Aspire AppHost, and `.github/workflows/publish.yml` deploy-azure job) against Azure best practices for security, reliability, and cost efficiency. If `$ARGUMENTS` is provided, review that specific file.

---

## 1. `azure.yaml` (azd Configuration)

Read `azure.yaml`.

**Check:**
- `services.app.host` is `containerapp` — this tells azd to deploy via Azure Container Apps (ACA), not App Service or AKS.
- `services.app.project` points to the AppHost csproj — if the path is wrong, `azd up` silently deploys nothing.
- No hardcoded subscription IDs, tenant IDs, or resource group names in `azure.yaml` — these belong in `azd env set` or GitHub secrets, not committed config.
- The `name` field matches the app name used in the CI/CD pipeline (`task-manager`) — a mismatch creates duplicate ACA environments.

---

## 2. Identity & Access (Managed Identity vs Keys)

Run:
```bash
grep -r "accountKey\|connectionString\|SharedAccessKey\|client_secret\|password" \
  azure.yaml aspire/ .github/workflows/publish.yml 2>/dev/null
```

**Check:**
- No storage account keys, SAS tokens, or connection strings in any tracked file. Azure Container Apps should authenticate to Azure services (Key Vault, ACR, Storage) using **Managed Identity**, not keys.
- The CI/CD `deploy-azure` job must use OIDC authentication (`azure/login@v2` with `client-id` / `tenant-id` / `subscription-id` from secrets) — **not** a service principal client secret (`AZURE_CREDENTIALS` JSON blob), which has no automatic rotation.
- Verify `publish.yml` `deploy-azure` job does not use `creds: ${{ secrets.AZURE_CREDENTIALS }}` (legacy SP approach).

**Evidence:**
```
✅ No connection strings or keys found in tracked files
❌ deploy-azure uses AZURE_CREDENTIALS JSON secret — migrate to OIDC federated identity
⚠️  ACR pull uses admin credentials — enable AcrPull role on the Container App managed identity
```

---

## 3. Secrets Management (Key Vault, not plain env vars)

**Check in `aspire/TaskManager.AppHost/Program.cs`:**
- `db-password` and `secret-key` parameters must resolve from **Azure Key Vault** in production, not from ACA environment variable plaintext. In `azure.yaml` or the generated Bicep, secrets must reference Key Vault secrets, not literal values.
- Verify the Aspire manifest (if generated) does not contain resolved literal secret values — it should contain `"{parameter.secret-key}"` style references.

Run:
```bash
cat aspire-manifest.json 2>/dev/null | python3 -c "
import json, sys
m = json.load(sys.stdin)
for name, res in m.get('resources', {}).items():
    for k, v in res.get('env', {}).items():
        if isinstance(v, str) and len(v) > 8 and '{' not in v:
            print(f'POSSIBLE LITERAL SECRET: {name}.{k} = {v[:4]}...')
"
```

---

## 4. Database: Azure Database for PostgreSQL vs Container

**Check `aspire/TaskManager.AppHost/Program.cs`:**
- In production, the `db` resource should be **Azure Database for PostgreSQL Flexible Server** (managed PaaS), not the `AddPostgres()` Docker container. The Docker container is correct for local dev; for Azure production, the AppHost should use `AddAzurePostgresFlexibleServer()` (from `Aspire.Hosting.Azure.PostgreSQL`) or the database URL should point to an Azure-managed instance.
- Flag if `AddPostgres("db").WithDataVolume()` is the only DB definition and there is no Azure-specific override — this will deploy a PostgreSQL container inside ACA which loses data on restart and is not production-appropriate.

**Recommended pattern:**
```csharp
// In Program.cs, use publisher-conditional configuration:
var postgres = builder.ExecutionContext.IsPublishMode
    ? builder.AddAzurePostgresFlexibleServer("db").AddDatabase("taskmanager")
    : builder.AddPostgres("db").WithDataVolume("taskmanager-data").AddDatabase("taskmanager");
```

---

## 5. Container App Scaling & Reliability

Read the generated Bicep files (if present in `infra/` after `azd provision`) or check if scaling config is in the AppHost.

**Check:**
- API container minimum replicas ≥ 1 — scaling to zero causes cold start latency for every first request.
- CPU and memory limits must be set explicitly — the default 0.5 CPU / 1Gi is too small for FastAPI + OTel in production; flag if no override is configured.
- Ingress for the `api` service must be `external: true` (or behind an APIM/gateway) — internal-only will prevent the frontend from reaching it.
- Ingress for `frontend` should be `external: true` with a custom domain configured.
- Health probes: ACA uses `/health` (liveness) and `/ready` (readiness) by default — verify these endpoints exist in the FastAPI app (`backend/app/main.py`):

```bash
grep -n "health\|ready" backend/app/main.py | head -10
```

---

## 6. Observability on Azure

**Check:**
- `OTEL_ENABLED=true` is set for the `api` container in the AppHost.
- The `OTLP_ENDPOINT` (or `OTEL_EXPORTER_OTLP_ENDPOINT`) points to **Azure Monitor / Application Insights** via the OTLP endpoint (`https://dc.services.visualstudio.com/...`) in production — not to the local Jaeger container.
- Aspire Dashboard is not accessible publicly — it should be disabled or restricted to internal access in production ACA environments.

---

## 7. CI/CD Pipeline (`publish.yml` — `deploy-azure` job)

Read `.github/workflows/publish.yml`, focus on the `deploy-azure` job.

**Check:**
- The job is gated by a named GitHub Environment (`production-azure`) with manual approval configured in the repo settings — flag if the environment name is missing or `if: false` was not removed.
- `azd deploy --no-prompt` is used (not `azd up` in CI — `azd up` also provisions infrastructure and is slower; `azd deploy` only deploys the app).
- The smoke test runs against the ACA URL, not `localhost` — verify `API_URL` is extracted from `azd env get-values`.
- The workflow uses `actions/setup-dotnet@v4` with version `9.x` — required for `azd` to build the Aspire manifest.

---

## 8. Cost Controls

**Check (advisory — no automated fix):**
- ACA consumption plan (serverless) vs dedicated — consumption is cost-efficient for variable load but has cold starts; dedicated has a floor cost. Flag if no choice is documented.
- PostgreSQL Flexible Server SKU: `Standard_B1ms` (burstable) is appropriate for this lab; `General_Purpose` is production-grade but significantly more expensive.
- Log Analytics workspace retention: default is 30 days. Flag if no retention policy is set (can accumulate cost).

---

## Output Format

```
── azure.yaml ───────────────────────────────────────
✅ host: containerapp
✅ No hardcoded subscription IDs
⚠️  name "task-manager" differs from ACA environment name — confirm they match

── Identity & Secrets ──────────────────────────────
✅ CI uses OIDC (client-id + tenant-id), not AZURE_CREDENTIALS JSON
❌ DB password set as plain ACA env var — store in Key Vault and reference via secretRef

── Database ─────────────────────────────────────────
⚠️  AddPostgres() container used in publish mode — data lost on ACA restart
   Fix: use IsPublishMode guard with AddAzurePostgresFlexibleServer()

── Scaling ──────────────────────────────────────────
✅ minReplicas: 1 configured
⚠️  No explicit CPU/memory limits — ACA defaults (0.5 CPU/1Gi) may be insufficient

── Observability ────────────────────────────────────
❌ OTLP_ENDPOINT still points to jaeger:4317 — update to Azure Monitor OTLP endpoint
```

Final summary:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Azure Deployment Review — Task Manager
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  azure.yaml correctness     ✅ / ⚠️ / ❌
  Identity (OIDC vs keys)    ✅ / ⚠️ / ❌
  Secrets (Key Vault)        ✅ / ⚠️ / ❌
  Database (PaaS vs container) ✅ / ⚠️ / ❌
  Scaling & reliability      ✅ / ⚠️ / ❌
  Observability              ✅ / ⚠️ / ❌
  CI/CD pipeline             ✅ / ⚠️ / ❌
  Cost controls (advisory)   ✅ / ⚠️ / ❌

  ❌ Must fix before production:  N
  ⚠️  Should fix:                N
  ✅ Passed:                     N
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

For every ❌: explain the attack vector or failure mode, quote the relevant config, and show the corrected version.
