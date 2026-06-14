Run an automated multi-tool security scan across all tiers. Executes SAST, dependency CVE checks, and secret pattern detection without modifying any files. Produces a risk-ranked report.

## Steps

### Step 1 — Python SAST (bandit)

From `backend/`:
```bash
bandit -r app/ -f json -ll 2>/dev/null
```

`-ll` means medium-and-above severity only (low findings are noisy in development).

Parse the JSON output and format findings as:

```
[HIGH]   app/routers/auth.py:47    B106 hardcoded_password_funcarg
[MEDIUM] app/database.py:12        B105 hardcoded_password_string
```

Group by severity: CRITICAL → HIGH → MEDIUM.

### Step 2 — Python dependency CVEs (pip-audit)

From `backend/`:
```bash
pip-audit --format json 2>/dev/null
```

For each vulnerability found:
```
[CVE-2024-XXXX] cryptography 42.0.1  →  upgrade to 42.0.5
  Severity: HIGH
  Description: ...
```

If no vulnerabilities: `✅ No known CVEs in Python dependencies`

### Step 3 — Frontend dependency CVEs (npm audit)

From `frontend/`:
```bash
npm audit --json 2>/dev/null
```

Report only `high` and `critical` findings (low/moderate are noise in dev):
```
[CRITICAL] lodash < 4.17.21   Prototype pollution   fix: npm audit fix
[HIGH]     axios < 1.6.0      SSRF                  fix: npm install axios@latest
```

If no high/critical: `✅ No high/critical CVEs in npm dependencies`

### Step 4 — Secret and credential pattern scan

Search all tracked files (excluding `.env`, `node_modules`, `.git`):

```bash
git ls-files | xargs grep -lnE \
  'password\s*=\s*["\x27][^"$\x27\{\}]{6,}|'\
  'secret[_\-]?key\s*=\s*["\x27][^"$\x27\{\}]{8,}|'\
  'api[_\-]?key\s*=\s*["\x27][^"$\x27\{\}]{8,}|'\
  'AKIA[0-9A-Z]{16}|'\
  'ghp_[a-zA-Z0-9]{36}|'\
  'sk-[a-zA-Z0-9]{32}|'\
  'postgresql://[^:]+:[^@$\{]{4,}@|'\
  'BEGIN (RSA |EC |DSA )?PRIVATE KEY' \
  2>/dev/null
```

For each match, show: file path, line number, matched pattern type (not the actual secret value).

**Exclude from scanning:** `*.md` files (false-positive-heavy), `tests/` fixtures, `.env.example` (it's a template).

### Step 5 — Attack surface inventory

Read the router files to produce a quick inventory of all endpoints and their auth status:

- For each `@router.get/post/patch/delete` in `backend/app/routers/`:
  - Check if `Depends(get_current_user)` or similar is present → `🔒 PROTECTED`
  - If not → `🌐 PUBLIC`

Flag any endpoint that looks like it should be protected but isn't (e.g., a `DELETE` or data-modifying `PATCH` without auth).

### Step 6 — Final risk summary

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Security Scan — Task Manager
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  SAST (bandit)              ✅ / ❌   0 / N findings
  Python CVEs (pip-audit)    ✅ / ❌   0 / N packages
  npm CVEs (npm audit)       ✅ / ❌   0 / N packages
  Secret patterns            ✅ / ❌   0 / N files
  Unprotected endpoints      ✅ / ❌   N public, N protected

  Overall risk level:  LOW / MEDIUM / HIGH / CRITICAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Risk level logic:
- `CRITICAL` — any CRITICAL CVE or confirmed secret in tracked files
- `HIGH` — any HIGH severity bandit finding or HIGH CVE
- `MEDIUM` — MEDIUM bandit findings or unauthenticated data-modifying endpoints
- `LOW` — all checks pass or only low-severity informational findings

For every finding, provide a specific remediation step.

## Context

- `bandit` and `pip-audit` must be installed: `pip install -e ".[dev]"` (they are in dev extras)
- If a tool is not installed, note the skip and show the install command
- Do NOT display actual secret values — only show the file:line and pattern category
- This skill only reads files; it never modifies anything
