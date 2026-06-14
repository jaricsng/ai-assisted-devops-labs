Scan the repository for hardcoded secrets, credentials, and sensitive values that should never be committed to version control. Checks tracked files, recent git history, and configuration hygiene.

This is a **read-only** scan — it never modifies files.

## Steps

### Step 1 — Scan tracked files for secret patterns

Search all git-tracked files (excluding binary files, `node_modules`, and `.git`):

```bash
git ls-files | grep -v 'node_modules\|\.git\|\.lock$\|\.png$\|\.jpg$\|\.ico$' | \
  xargs grep -InE \
    'password\s*[=:]\s*["\x27][^"$\x27\{\}<>\s]{6,}["\x27]|'\
    'secret[_-]?key\s*[=:]\s*["\x27][^"$\x27\{\}<>\s]{8,}["\x27]|'\
    'api[_-]?key\s*[=:]\s*["\x27][^"$\x27\{\}<>\s]{8,}["\x27]|'\
    'auth[_-]?token\s*[=:]\s*["\x27][A-Za-z0-9+/]{16,}["\x27]|'\
    'AKIA[0-9A-Z]{16}|'\
    'ghp_[a-zA-Z0-9]{36,}|'\
    'ghs_[a-zA-Z0-9]{36,}|'\
    'sk-[a-zA-Z0-9]{32,}|'\
    'xoxb-[0-9]{11}-[0-9]{11}-[a-zA-Z0-9]{24}|'\
    'postgresql://[^:@\s\{]+:[^@\s\{]{4,}@|'\
    'mysql://[^:@\s\{]+:[^@\s\{]{4,}@|'\
    'BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY' \
  2>/dev/null
```

For each match, report: file path, line number, and the **pattern category** (e.g., "possible hardcoded password", "AWS access key pattern", "private key") — do NOT print the matched value itself.

**Safe to ignore (whitelist):**
- `.env.example` — this is a template, not a real secret
- `docs/` — documentation examples with placeholder values like `<your-api-key>`
- `tests/conftest.py` — test fixtures like `SECRET_KEY: ci-test-secret-key` in `env:` blocks (they are not real secrets)
- Lines that contain only the variable name (e.g., `SECRET_KEY=` with no value)

### Step 2 — Check git history for accidentally committed secrets

Search the last 50 commits for secret patterns in diffs:

```bash
git log --oneline -50 --all | awk '{print $1}' | \
  xargs -I{} git show {} -- 2>/dev/null | \
  grep -E '^\+.*password\s*=|^\+.*secret_key\s*=|^\+.*AKIA[0-9A-Z]{16}|^\+.*ghp_' \
  2>/dev/null | head -20
```

If any matches are found: report the commit hash, file, and pattern category. Then advise:
> "A secret found in git history remains exposed even after deletion. Use `git filter-repo` to rewrite history, then rotate the secret immediately."

### Step 3 — Verify .gitignore covers sensitive files

Check that these patterns exist in the root `.gitignore`:

- `.env` (or `.env.*` except `.env.example`)
- `*.pem`, `*.key`, `*.p12`, `*.pfx`
- `backend/.env`
- `frontend/.env.local`

Report any missing pattern as a ⚠️ warning.

### Step 4 — Check environment variable defaults

Read `backend/app/config.py`. For every field in the `Settings` class:
- If a secret field (`secret_key`, `database_url`, `password`) has a non-empty default value that isn't an obvious placeholder (`"change-me-in-production"`, `"dev-only"`, `"test-secret"`), flag it as ❌.
- If `SECRET_KEY` has any hardcoded default at all (even a placeholder), note it as a ⚠️ — the correct pattern is to make it required (no default) so the app fails fast if it's missing.

### Step 5 — Check Docker Compose for exposed credentials

Read `docker-compose.yml`:
- If database credentials (`POSTGRES_PASSWORD`, etc.) are hardcoded values rather than `${VAR}` references, flag them as ⚠️. (Hardcoded dev credentials are common and low-risk in local-only compose files, but note they should never appear in production compose files.)
- If any service exposes a port that should be internal (e.g., the database on port 5432 bound to `0.0.0.0` instead of `127.0.0.1`), note it.

### Step 6 — Summary

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Secrets Scan — Task Manager
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Tracked files scanned    ✅ / ❌   N matches
  Git history (last 50)    ✅ / ❌   N matches
  .gitignore coverage      ✅ / ⚠️   N missing patterns
  Config defaults          ✅ / ⚠️   N weak defaults
  Docker Compose           ✅ / ⚠️   N hardcoded values
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**If any ❌ (real secret) is found:** treat it as an incident.
1. Rotate the secret immediately (generate a new value).
2. Revoke the old value in the service that issued it.
3. Rewrite git history with `git filter-repo --path <file> --invert-paths` or use BFG Repo Cleaner.
4. Force-push with `--force-with-lease` only after confirming with the team.
5. Consider the secret compromised until confirmed revoked.

## Context

- This skill prints pattern categories, never the actual secret values
- "Secret" in test fixtures (`ci-test-secret-key`) is not a real secret — it has no access to real systems
- The purpose is to ensure production secrets (real JWT signing keys, real DB passwords) never enter version control
