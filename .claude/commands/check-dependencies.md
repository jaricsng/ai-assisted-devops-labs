Audit Python and JavaScript dependencies for known CVEs, abandoned packages, and supply-chain risks. This is the A06 (Vulnerable and Outdated Components) check from the OWASP Top 10.

## Steps

### Step 1 — Python dependency audit (pip-audit)

From `backend/`:
```bash
pip-audit --format json 2>/dev/null
```

For each vulnerability found, report:

```
❌ [CVE-2024-XXXXX]  CRITICAL
   Package:     cryptography 42.0.1
   Fixed in:    42.0.5
   Description: RSA decryption timing side-channel allows key recovery
   Fix:         pip install "cryptography>=42.0.5"
   Update in:   backend/pyproject.toml → "cryptography>=42.0.5"
```

Group by severity: CRITICAL → HIGH → MODERATE → LOW.

If pip-audit is not installed: `pip install pip-audit`

### Step 2 — JavaScript dependency audit (npm audit)

From `frontend/`:
```bash
npm audit --json 2>/dev/null
```

Report only `high` and `critical` vulnerabilities (low/moderate in devDependencies are rarely exploitable in the browser):

```
❌ [GHSA-XXXX-XXXX-XXXX]  HIGH
   Package:     vite < 5.4.6
   Path:        vite → @vitejs/plugin-react
   Description: Path traversal in dev server static file serving
   Fix:         npm install vite@latest
```

Also run:
```bash
npm outdated --json 2>/dev/null
```

Flag packages that are more than **2 major versions** behind (e.g., React 16 when 18 is current) as ⚠️ maintenance risk.

### Step 3 — Check for abandoned or suspicious packages

Read `backend/pyproject.toml` and `frontend/package.json`. For each direct dependency:

Flag as ⚠️ if:
- The package name is a very close misspelling of a popular package (typosquatting risk): e.g., `reqeusts` instead of `requests`, `fast-api` instead of `fastapi`
- The package has no known maintainer (check against known well-maintained lists)

List all direct dependencies and note any that look unusual or unexpected for this project's tech stack.

### Step 4 — Check lock file hygiene

**Python:**
```bash
# Does a compiled requirements file exist?
ls backend/requirements*.txt 2>/dev/null || echo "no compiled requirements"
```

Note: `pyproject.toml` with `>=` bounds is used in this project. In production, `pip-compile` (from `pip-tools`) should generate a `requirements.txt` with pinned exact versions. Flag if no pinned requirements file exists for production use.

**JavaScript:**
```bash
# Is package-lock.json committed?
git ls-files frontend/package-lock.json | wc -l
```

`package-lock.json` must be committed (it pins exact dependency versions). If not tracked: ❌ supply-chain risk.

```bash
# Does package-lock.json match package.json? (detects manual edits)
cd frontend && npm ci --dry-run 2>&1 | grep -i "error\|warn" | head -5
```

### Step 5 — CI pipeline dependency scanning

Read `.github/workflows/ci.yml`. Check whether there is a dedicated security job running:
- `pip-audit` on the Python dependencies
- `npm audit --audit-level=high` on the JavaScript dependencies

If neither is present, flag ⚠️ and note: "Dependency CVEs are not checked in CI. Add a `security` job to prevent vulnerable packages from reaching production."

### Step 6 — Summary and remediation plan

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Dependency Audit — Task Manager
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Python (pip-audit)
    Critical:  N packages
    High:      N packages
    Moderate:  N packages (informational)

  JavaScript (npm audit)
    Critical:  N packages
    High:      N packages

  Lock file hygiene
    package-lock.json committed:  ✅ / ❌
    requirements pinned:          ✅ / ⚠️

  CVE scanning in CI:  ✅ / ⚠️

  Overall:  ✅ CLEAN  /  ⚠️ N warnings  /  ❌ N vulnerabilities
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Provide an ordered remediation list: fix critical first, then high, then address lock file and CI gaps.

## Context

- `pip-audit` is in the project's dev dependencies (`pip install -e ".[dev]"`)
- `npm audit` is built into npm — no install needed
- CVE severity ratings come from the NVD (National Vulnerability Database); pip-audit and npm audit both use these
- A CVE in a `devDependency` is generally lower risk than one in a production dependency, but flag both
