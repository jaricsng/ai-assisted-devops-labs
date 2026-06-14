Run a structured penetration test against the Task Manager API and report findings.

If `$ARGUMENTS` specifies a focus area (`authentication`, `access-control`, `injection`, `design`), test only that area.
If no argument is given, run the full automated check suite and offer to run ZAP afterward.

## Authorization Notice

This skill targets `http://localhost:8000` only — your own running instance.
Never point it at any other system without explicit written authorisation.

## Steps

### Step 1 — Verify the API is running

```bash
curl -sf http://localhost:8000/health || echo "API not reachable — run: docker compose up -d"
```

If not reachable, stop and tell the user to start the stack.

### Step 2 — Run the automated manual checks

```bash
chmod +x pen-tests/manual-checks.sh
./pen-tests/manual-checks.sh http://localhost:8000
```

If `$ARGUMENTS` is set, scope the run to the relevant section:

| Argument | Focus | Checks run |
|----------|-------|-----------|
| `authentication` | A02, A07 | JWT alg:none, tampered token, weak/empty password |
| `access-control` | A01 | IDOR read, IDOR write, unauthenticated access |
| `injection` | A03 | SQL injection in task title, XSS in project name |
| `design` | A04 | Status transition bypass, rate limiting, user enumeration |

For focused runs, call the script but only summarise findings for that OWASP category.

### Step 3 — Parse findings

For every `FAIL ❌` line in the script output:

1. Identify the OWASP category (A01–A10)
2. Read the relevant source file to locate the vulnerable code:
   - A01 IDOR → `backend/app/repositories/` — does the query filter by `owner_id`?
   - A02 JWT → `backend/app/middleware/auth.py` or equivalent — which library verifies the token?
   - A03 Injection → `backend/app/repositories/` — are queries using ORM parameterisation or raw SQL?
   - A04 Design → `backend/app/services/task_service.py` — is the transition guard server-side?
   - A04 Rate limiting → `backend/app/main.py` — is `slowapi` or similar middleware configured?
   - A05 CORS → `backend/app/main.py` — what are the `allow_origins` values?
   - A07 Auth → `backend/app/schemas/user.py` — what are the password validation rules?

3. Produce a finding block for each FAIL:

```
[SEVERITY] OWASP-AXX: <Finding title>
Evidence:  HTTP <status> when expected <expected status>
Code path: <file>:<line> — <description of issue>
Fix:       <specific code change or configuration>
CVSS est.: <score> (<rating>)
```

### Step 4 — Offer ZAP scan (full run only)

After the manual checks, ask:

> "Run OWASP ZAP baseline scan for automated header and passive analysis? This takes 2–5 minutes and requires Docker. (yes/no)"

If yes:
```bash
chmod +x pen-tests/zap-scan.sh
./pen-tests/zap-scan.sh http://localhost:8000
```

After ZAP completes, read the JSON report and add any HIGH or MEDIUM ZAP alerts to the findings list.

### Step 5 — Produce a pen test report summary

After all checks, output a structured report:

```
╔══════════════════════════════════════════════════════════╗
║     Task Manager API — Penetration Test Summary          ║
║     Tested: http://localhost:8000                        ║
╚══════════════════════════════════════════════════════════╝

CHECKS PASSED:  N
CHECKS FAILED:  N
OVERALL RISK:   LOW | MEDIUM | HIGH | CRITICAL

──────────────────────────────────────────────────────────
FINDINGS
──────────────────────────────────────────────────────────

[CRITICAL] A02: JWT alg:none attack accepted
  Evidence:  HTTP 200 on unsigned token (expected 401)
  Fix:       In auth dependency, pass algorithms=["HS256"] to jwt.decode()
             and never accept tokens with alg="none"
  CVSS est.: 9.1 (Critical)

[HIGH]  A01: IDOR — User B can read User A's project
  Evidence:  HTTP 200 on /projects/<id> with User B's token
  Fix:       Add WHERE owner_id = :current_user_id to project_repository.get_by_id()
  CVSS est.: 7.5 (High)

[INFO]  A03: SQL injection — no vulnerability found
  Evidence:  HTTP 201 (payload stored as literal text)
  Note:      SQLAlchemy ORM prevents injection; raw SQL queries are the risk to watch

──────────────────────────────────────────────────────────
REMEDIATION PRIORITY
──────────────────────────────────────────────────────────
1. Fix CRITICAL items before any deployment
2. Fix HIGH items in current sprint
3. Document accepted risks for LOW/INFO items in docs/adr/

──────────────────────────────────────────────────────────
NEXT STEPS
──────────────────────────────────────────────────────────
- Run the full ZAP scan for header and passive analysis
- After fixing findings, re-run: ./pen-tests/manual-checks.sh
- Create docs/pen-test-report.md with full evidence for each finding
- Commit: security: fix <finding-name> and add pen test report
```

For each CRITICAL or HIGH finding, offer to fix it immediately if the code path is clear.

## Context

- `pen-tests/manual-checks.sh` — automated curl-based checks (A01–A07)
- `pen-tests/zap-scan.sh` — Docker-based ZAP scanner (baseline or full mode)
- `pen-tests/reports/` — ZAP HTML and JSON reports land here
- Target is always `http://localhost:8000` — never any other host
- Load tests create real users and data — the pen test script creates its own isolated test users
