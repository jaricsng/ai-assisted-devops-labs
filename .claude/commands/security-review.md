Perform an AI-powered security review of the changed code (or a specific file/path if provided as `$ARGUMENTS`) against the OWASP Top 10 (2021). This goes deeper than automated tools — it reads the code and reasons about logic-level vulnerabilities that scanners miss.

If `$ARGUMENTS` is provided, review that file or directory.
Otherwise, review all files changed since `main`: `git diff main...HEAD --name-only`

---

## OWASP Top 10 Review Checklist

Work through each category. For each one: read the relevant source files, evaluate the controls in place, and report the finding with severity and evidence.

---

### A01 — Broken Access Control

**What to check:**
1. Every protected route has `Depends(get_current_user)` (or equivalent). Read `app/routers/` and verify no data-modifying endpoint (`POST`, `PATCH`, `DELETE`) is missing auth.
2. **IDOR check**: When a route fetches a resource by ID (e.g., `GET /projects/{id}`), verify the query includes `WHERE owner_id = current_user.id` (or equivalent). A query like `SELECT * FROM projects WHERE id = ?` with no owner check is an IDOR.
3. Horizontal privilege escalation: can User A modify User B's tasks? Trace the `PATCH /tasks/{id}` flow from router → service → repository and confirm ownership is checked before the update.
4. CORS: read `app/main.py` and verify `allow_origins` is not `["*"]` in production configuration.

**Evidence format:**
```
✅ A01 — All 8 data-modifying routes require authentication
⚠️  A01 — GET /projects/{id} does not verify the project belongs to current_user (IDOR risk)
❌ A01 — PATCH /tasks/{id} updates the task without checking assignee or project ownership
```

---

### A02 — Cryptographic Failures

**What to check:**
1. Password hashing: find all calls to `passlib` in `app/`. Verify bcrypt is used (not MD5, SHA1, SHA256 without salt, or plain storage).
2. JWT secret: find where `SECRET_KEY` is used. Verify it comes from `settings.secret_key` (env var), not a hardcoded string.
3. JWT algorithm: verify `algorithm` is `HS256` or stronger (not `none` — the "none" algorithm attack).
4. Token expiry: find `access_token_expire_minutes` in config. Flag if it is `0` (never expires) or longer than 24 hours.
5. Sensitive data in JWT payload: find where the JWT payload is constructed. Flag any inclusion of passwords, full email addresses, or internal IDs that shouldn't be in a client-readable token (JWT is base64, not encrypted).
6. HTTPS: note that TLS termination is handled by the infrastructure layer (not FastAPI), but flag if `allow_origins` includes `http://` origins in a production context.

---

### A03 — Injection

**What to check:**
1. SQL injection: search `app/repositories/` and `app/services/` for any `text(f"... {variable}")` patterns. Every SQLAlchemy `text()` call must use bound parameters (`:param`), not f-string interpolation.
2. Verify all query parameters go through Pydantic schemas before reaching the database. Read the relevant router and confirm Pydantic is the entry point.
3. Command injection: search for `subprocess`, `os.system`, `eval`, `exec` in the entire `app/` directory. Flag any use.
4. Template injection: if Jinja2 or similar is used (e.g., for email templates), verify user input is never passed as a template string.

---

### A04 — Insecure Design

**What to check:**
1. Business logic enforcement on the server: the task status state machine must be enforced in `app/services/task_service.py`, not only in the frontend. Verify that a direct `PATCH /tasks/{id}` with an invalid transition returns 422 even if the frontend is bypassed.
2. Rate limiting on authentication endpoints: check `app/routers/auth.py`. If there is no rate limiting on `POST /auth/login`, flag it — brute-force attacks are trivial without it.
3. User enumeration: check the login endpoint's error response. Returning `"email not found"` vs `"wrong password"` lets attackers enumerate valid emails. The correct response is a generic `"invalid credentials"` for both cases.
4. Mass assignment: Pydantic schemas must define exactly which fields are accepted. Verify that `UserCreate`, `TaskCreate`, and `ProjectCreate` schemas do not accept `id`, `created_at`, or privilege fields like `is_admin`.

---

### A05 — Security Misconfiguration

**What to check:**
1. Read `app/main.py` and `app/config.py`:
   - `DEBUG` or `echo=True` in SQLAlchemy must only be enabled when `ENVIRONMENT == "development"` — verify this condition.
   - `SECRET_KEY` default: if `settings.secret_key` has a default value like `"change-me"`, flag it. Secrets must have no default (required env var) or be rejected if they match a known-weak value.
2. Read `docker-compose.yml`: database credentials (`POSTGRES_USER`, `POSTGRES_PASSWORD`) must come from env vars in production, not hardcoded in the compose file for non-dev environments.
3. Error responses: FastAPI's default 422 response body can leak field names and internal schema details. Verify sensitive field names (like `hashed_password`) are not in any response schema.
4. HTTP headers: note that standard security headers (HSTS, X-Content-Type-Options, X-Frame-Options) require a reverse proxy (nginx/Caddy) in front of FastAPI — document this if not already noted.

---

### A06 — Vulnerable and Outdated Components

**What to check:**
1. Run `pip-audit` in `backend/` and `npm audit` in `frontend/` (or note results from `/security-scan` if already run).
2. Check `backend/pyproject.toml`: dependencies using `>=` without upper bounds (e.g., `fastapi>=0.115`) are safe for minor bumps but can pull in breaking changes. This is acceptable in a lab; note for production.
3. Check `frontend/package-lock.json` is committed — this pins exact versions and is essential for reproducible builds.

---

### A07 — Identification and Authentication Failures

**What to check:**
1. Find `create_access_token` in `app/services/auth_service.py` or similar. Verify `exp` (expiry) is set.
2. Verify the token is passed as `Authorization: Bearer <token>` (header), not as a query parameter (`?token=...` leaks tokens in server logs and browser history).
3. Check `get_current_user` in `app/routers/deps.py`: verify it raises `401` on an invalid token, not `500` or a generic error.
4. Password policy: `UserCreate` Pydantic schema — verify minimum password length is enforced (≥8 characters). If not, flag it.
5. Logout: JWT is stateless, so there's no server-side logout. Note this design trade-off and whether a token blocklist is needed.

---

### A08 — Software and Data Integrity Failures

**What to check:**
1. `package-lock.json` exists and is committed (prevents dependency substitution attacks).
2. CI pipeline (`ci.yml`) uses pinned action versions (`@v4`, not `@main` or `@latest`). Check each `uses:` line.
3. Docker base images: check `backend/Dockerfile` and `frontend/Dockerfile`. Using `python:3.12` (no digest pin) vs `python:3.12-slim@sha256:...` (digest-pinned). Note the trade-off.

---

### A09 — Security Logging and Monitoring Failures

**What to check:**
1. Auth failures: find the login handler. Verify a failed login attempt is logged (structlog event like `login_failed`) at `WARNING` level with the attempted email.
2. Privileged actions: verify task status changes and project deletions are logged.
3. Secrets in logs: search `app/` for any `logger.*password` or `logger.*token` calls that might log sensitive values.
4. No PII in logs: verify user email addresses are not logged on every request (only on explicit auth events is acceptable).
5. OTel: confirm `setup_telemetry()` is called and traces are being exported — this is the monitoring infrastructure.

---

### A10 — Server-Side Request Forgery (SSRF)

**What to check:**
1. Search `app/` for `httpx`, `requests`, `aiohttp`, or `urllib`. If the application makes outbound HTTP calls:
   - Is the destination URL controlled by user input? If so, flag as critical SSRF risk.
   - Is there an allowlist of valid destinations?
2. If no outbound HTTP calls exist currently, note: "No SSRF surface currently. If webhooks or integrations are added in future, validate destination URLs against an allowlist."

---

## Output Format

For each OWASP category produce:

```
A01 — Broken Access Control
  ✅ All mutating routes require authentication
  ❌ IDOR: GET /projects/{id} at routers/projects.py:34 — no ownership check
     Fix: Add `WHERE owner_id = current_user.id` to the repository query
  ⚠️  CORS allows localhost:5173 — ensure this is restricted in production config
```

Final summary table:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  OWASP Top 10 Review — Task Manager
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  A01  Broken Access Control          ✅ / ⚠️ / ❌
  A02  Cryptographic Failures         ✅ / ⚠️ / ❌
  A03  Injection                      ✅ / ⚠️ / ❌
  A04  Insecure Design                ✅ / ⚠️ / ❌
  A05  Security Misconfiguration      ✅ / ⚠️ / ❌
  A06  Vulnerable Components          ✅ / ⚠️ / ❌
  A07  Auth Failures                  ✅ / ⚠️ / ❌
  A08  Data Integrity Failures        ✅ / ⚠️ / ❌
  A09  Logging & Monitoring           ✅ / ⚠️ / ❌
  A10  SSRF                           ✅ / ⚠️ / ❌

  ❌ Critical (must fix):  N
  ⚠️  Warnings (should fix): N
  ✅ Passed:               N
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

For every ❌ finding: quote the specific line of code, explain the attack vector (what an attacker could do), and provide the corrected code.
For every ⚠️ finding: explain the risk and the recommended fix.
