Review the .NET Aspire AppHost configuration in `aspire/TaskManager.AppHost/` against best practices for orchestration correctness, secret hygiene, service wiring, and multi-cloud readiness. If `$ARGUMENTS` is provided, review that specific file. Otherwise review all files under `aspire/`.

---

## 1. AppHost Project File (`TaskManager.AppHost.csproj`)

Read `aspire/TaskManager.AppHost/TaskManager.AppHost.csproj`.

**Check:**
- `<IsAspireHost>true</IsAspireHost>` is present (required for Aspire tooling to recognise the project)
- `<Sdk Name="Aspire.AppHost.Sdk">` is specified with a pinned version — flag `*` or `latest` wildcards
- `<UserSecretsId>` is set (required for `dotnet user-secrets` to work)
- Package versions for `Aspire.Hosting.AppHost` and `Aspire.Hosting.PostgreSQL` match the SDK version exactly — version mismatches cause cryptic build failures
- No cloud provider SDKs (`Aspire.Hosting.AWS`, `Aspire.Hosting.Azure.*`) in the csproj unless intentional; they pull in large transitive dependencies

**Evidence format:**
```
✅ IsAspireHost: true
✅ SDK pinned: Aspire.AppHost.Sdk 9.1.0
⚠️  Aspire.Hosting.AppHost version (9.0.0) does not match SDK version (9.1.0)
❌ UserSecretsId missing — dotnet user-secrets will fail at runtime
```

---

## 2. Service Wiring (`Program.cs`)

Read `aspire/TaskManager.AppHost/Program.cs`.

### 2a. Dependency ordering
- Every service that depends on another must use `.WaitFor(dependency)`. Verify:
  - `api` calls `.WaitFor(postgres)` — FastAPI will crash at startup if the DB is not ready
  - `frontend` calls `.WaitFor(api)` — avoids React showing API errors on first load
- Flag any service that uses a downstream resource but is missing `.WaitFor()`

### 2b. Endpoint references for non-.NET services
- Non-.NET containers (Python, Node) cannot use Aspire service discovery automatically. Verify that every environment variable referencing another service is wired using `ReferenceExpression.Create(...)` or an explicit `GetEndpoint()` call — **never a hardcoded `localhost:PORT`** string literal (it will break when Aspire assigns a different port).
- Specific check: `VITE_API_URL` must use `api.GetEndpoint("http")`, not `"http://localhost:8000"`.
- Specific check: `DATABASE_URL` must use `ReferenceExpression.Create(...)` referencing the postgres endpoint and the `db-password` parameter, not a hardcoded connection string.

### 2c. DATABASE_URL format
- Python's SQLAlchemy async requires `postgresql+asyncpg://` prefix. Aspire's built-in Npgsql connection string uses `Host=...;Port=...` format. Verify the `DATABASE_URL` environment variable is explicitly constructed with the `+asyncpg` prefix — Aspire's `WithReference(database)` alone injects the wrong format for Python.

### 2d. Secrets vs plain parameters
- Sensitive values (`db-password`, `secret-key`) must use `builder.AddParameter("name", secret: true)` — the `secret: true` flag masks the value in the Aspire Dashboard.
- Flag any secret passed via a plain `WithEnvironment("KEY", "literal-value")` string.
- Non-secret config (e.g., `ENVIRONMENT`, `OTEL_ENABLED`) should be plain `.WithEnvironment()` strings — no need to make them parameters.

### 2e. Data persistence
- PostgreSQL must use `.WithDataVolume("taskmanager-data")` (or equivalent named volume). A missing `WithDataVolume()` means the database is wiped every time Aspire restarts — flag this.

### 2f. Resource naming
- Aspire resource names (`"db"`, `"api"`, `"frontend"`) must be lowercase kebab-case. They become DNS labels in Docker networking — uppercase or underscores will cause resolution failures.

---

## 3. Settings Files

Read `aspire/TaskManager.AppHost/appsettings.json` and `appsettings.Development.json`.

**Check:**
- `appsettings.Development.json` may contain default parameter values for local dev convenience, but must **not** be used in a production environment. Verify the file is in `.gitignore` OR that the values are clearly placeholder/dev-only values (never production passwords).
- `appsettings.json` should only contain logging config and non-sensitive settings.
- The `Parameters` section keys must exactly match the parameter names used in `Program.cs` (`"db-password"`, `"secret-key"`) — a mismatch silently uses an empty string and causes confusing runtime errors.
- Flag if `appsettings.Development.json` contains a `secret-key` value shorter than 32 characters — JWTs signed with a short key are brute-forceable.

---

## 4. ServiceDefaults Project

Read `aspire/TaskManager.ServiceDefaults/Extensions.cs`.

**Check:**
- `AddOpenTelemetry()` is configured with both `.WithMetrics()` and `.WithTracing()` — missing one means incomplete observability.
- The OTLP exporter is only enabled when `OTEL_EXPORTER_OTLP_ENDPOINT` is set — do not default to exporting blindly.
- `MapDefaultEndpoints()` registers `/health` (liveness) and `/ready` (readiness) — both must exist for cloud orchestrators.
- Note: ServiceDefaults is only useful if .NET services are added in future. It has no effect on the current Python/Node services — confirm there is a comment to this effect in the file.

---

## 5. Manifest Generation Readiness

Run:
```bash
dotnet build aspire/TaskManager.AppHost/TaskManager.AppHost.csproj --nologo -q 2>&1
```

If the Aspire workload is installed, also run:
```bash
dotnet run --project aspire/TaskManager.AppHost \
  -- --publisher manifest --output-path /tmp/aspire-manifest.json 2>&1 | tail -5
cat /tmp/aspire-manifest.json 2>/dev/null | python3 -m json.tool --no-indent | head -40
```

**Check the manifest output for:**
- All three resources present: `db`, `api`, `frontend`
- `"type": "dockerfile.v0"` for api and frontend (not `"project.v0"` — that's for .NET projects)
- Connection string expressions are present as `"{parameter.db-password}"` style references, not resolved literal values (resolved literals would mean secrets leaked into the manifest)

---

## 6. Dockerfile Paths

Verify the `contextPath` and `dockerfilePath` references in `Program.cs` point to valid locations relative to the AppHost project:

```bash
ls /Users/jaricsng/dev/ai-assisted/learn/claudecode/task-manager/backend/Dockerfile
ls /Users/jaricsng/dev/ai-assisted/learn/claudecode/task-manager/frontend/Dockerfile
```

- `AddDockerfile("api", "../../backend")` → resolves to `backend/Dockerfile` from the project root ✅
- `AddDockerfile("frontend", "../../frontend")` → resolves to `frontend/Dockerfile` from the project root ✅
- Flag if paths are wrong — the AppHost will fail with a cryptic "file not found" error at startup.

---

## Output Format

For each section produce findings:

```
── Program.cs ─────────────────────────────────────
✅ WaitFor: api waits for postgres, frontend waits for api
✅ DATABASE_URL uses ReferenceExpression with asyncpg prefix
⚠️  VITE_API_URL: uses hardcoded "http://localhost:8000" — breaks when port changes
❌ db-password passed as plain string literal — use AddParameter("db-password", secret: true)
```

Final summary:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Aspire Best Practice Review — Task Manager
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Project file          ✅ / ⚠️ / ❌
  Service wiring        ✅ / ⚠️ / ❌
  Secret hygiene        ✅ / ⚠️ / ❌
  Settings files        ✅ / ⚠️ / ❌
  ServiceDefaults       ✅ / ⚠️ / ❌
  Manifest readiness    ✅ / ⚠️ / ❌
  Dockerfile paths      ✅ / ⚠️ / ❌

  ❌ Must fix:     N
  ⚠️  Should fix:  N
  ✅ Passed:       N
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

For every ❌ finding: quote the violating line, explain what breaks at runtime, and show the corrected code.
For every ⚠️ finding: explain the risk and the recommended change.
