Generate a STRIDE threat model for the Task Manager application or a specific feature. This is a shift-left security practice: identifying threats during design (or code review) rather than after deployment.

If `$ARGUMENTS` is provided, focus the threat model on that feature or component (e.g., `/threat-model authentication`, `/threat-model task-status-transition`, `/threat-model file-upload`).
Otherwise, produce a full application-level threat model.

---

## What is STRIDE?

STRIDE is a threat categorisation framework developed at Microsoft. Each letter maps to a threat category:

| Letter | Threat | What an attacker gains |
|--------|--------|----------------------|
| **S** | Spoofing | Pretending to be someone else (identity theft) |
| **T** | Tampering | Modifying data or code without authorisation |
| **R** | Repudiation | Denying having performed an action |
| **I** | Information Disclosure | Reading data they shouldn't have access to |
| **D** | Denial of Service | Making the system unavailable |
| **E** | Elevation of Privilege | Gaining permissions beyond what's authorised |

---

## Step 1 — Identify assets and trust boundaries

Read the following files to understand the system:
- `CLAUDE.md` — architecture overview
- `docker-compose.yml` — service topology and network
- `backend/app/main.py` — entry points and middleware
- `backend/app/models/` — data assets
- `backend/app/routers/` — API surface
- `docs/adr/` — recorded architecture decisions

Produce an **asset inventory**:
```
Assets (things worth protecting):
  - User credentials (email + bcrypt hash)
  - JWT signing secret
  - Project and task data (potentially confidential business data)
  - Database connection string

Trust boundaries:
  - Internet → FastAPI (port 8000) [untrusted → trusted]
  - FastAPI → PostgreSQL (port 5432) [trusted → trusted, but DB should not be internet-exposed]
  - React → FastAPI [untrusted client → trusted API]
```

---

## Step 2 — Enumerate data flows

For each major user flow, describe the data path and mark where it crosses a trust boundary:

```
Login flow:
  Browser → [BOUNDARY] → POST /auth/login → auth_service.authenticate()
    → user_repository.get_by_email() → PostgreSQL
    → bcrypt.checkpw(password, hash) → JWT issued
    ← Bearer token returned to browser

Task status change:
  Browser (with JWT) → [BOUNDARY] → PATCH /tasks/{id}
    → get_current_user() validates JWT
    → task_service.update_status() checks VALID_TRANSITIONS
    → task_repository.update() → PostgreSQL
```

---

## Step 3 — Apply STRIDE to each flow

For each data flow, reason through all six threat categories and produce findings:

### Format for each threat:

```
[S] Spoofing — Authentication endpoint
  Threat:     Attacker uses a stolen JWT to impersonate another user
  Likelihood: MEDIUM (JWTs can be stolen via XSS or insecure storage)
  Impact:     HIGH (full account takeover)
  Control:    JWT validated on every request via get_current_user()
  Gap:        No token revocation — a stolen token is valid until expiry
  Mitigation: Implement short expiry (30 min ✅) + refresh token rotation,
              or a token blocklist for logout
```

Work through **all six categories** for each major flow. Not every category will apply — if a threat is genuinely not applicable, state why (e.g., "T — Tampering on GET /health: no data written, not applicable").

---

## Step 4 — Application-level STRIDE analysis

Regardless of the specific feature, always cover these application-level threats:

**S — Spoofing**
- JWT token theft (XSS, insecure storage, log leakage)
- Credential stuffing against /auth/login
- Social engineering (out of scope for code review)

**T — Tampering**
- SQL injection in user-controlled inputs
- IDOR: modifying another user's tasks by guessing IDs
- JWT payload tampering (alg:none attack)
- Direct database manipulation bypassing the API

**R — Repudiation**
- User denies performing a status transition
- Admin denies deleting a project
- Mitigation: structured logs with user_id, timestamp, and action (already implemented via structlog)

**I — Information Disclosure**
- User can read another user's projects (IDOR on read)
- Error responses exposing stack traces or internal field names
- Logs containing passwords, tokens, or PII
- Database credentials in environment variables accessible to other containers

**D — Denial of Service**
- Unauthenticated endpoints hit at high rate (no rate limiting)
- Very large request bodies (no body size limit)
- Slow DB queries (N+1, missing indexes) causing connection pool exhaustion
- POST /auth/register spammed to fill the users table

**E — Elevation of Privilege**
- Regular user accessing admin-only operations (if admin role exists)
- JWT `role` claim manipulation if role is encoded in the token
- Alembic `upgrade head` run by a low-privilege DB user

---

## Step 5 — Risk matrix

After identifying all threats, place each in a risk matrix:

```
                    IMPACT
                Low    Medium   High    Critical
           ┌────────┬────────┬────────┬──────────┐
High       │        │  ⚠️     │  ❌    │  ❌      │
LIKELIHOOD │        │        │        │          │
Medium     │  ✅    │  ⚠️     │  ❌    │  ❌      │
           │        │        │        │          │
Low        │  ✅    │  ✅    │  ⚠️    │  ❌      │
           └────────┴────────┴────────┴──────────┘
```

Place each identified threat (by ID: S1, T1, I1, etc.) in the appropriate cell.

---

## Step 6 — Mitigation backlog

Produce a prioritised list of recommended mitigations, ordered by risk level:

```
Priority 1 — CRITICAL / HIGH risk (address before production)
  [D1] No rate limiting on POST /auth/login
       → Add slowapi or similar rate limiting: pip install slowapi
       → Limit to 5 attempts per IP per minute

  [T2] No request body size limit
       → Add to main.py: app.add_middleware(...)

Priority 2 — MEDIUM risk (address in next sprint)
  [S3] JWT not revocable on logout
       → Implement short-lived access tokens (30 min ✅) + refresh tokens
       → Or maintain a Redis blocklist of revoked JIDs

Priority 3 — LOW risk / accepted
  [R1] No cryptographic proof of user actions (only logs)
       → Accepted: structlog provides sufficient audit trail for this app's risk level
```

---

## Output Format

1. **Asset inventory** (Step 1)
2. **Data flow diagram** in text/Mermaid (Step 2)
3. **STRIDE findings** with Threat ID, category, likelihood, impact, existing control, gap, mitigation (Step 3–4)
4. **Risk matrix** (Step 5)
5. **Mitigation backlog** ordered by priority (Step 6)
6. **One-line summary**: "N threats identified: N critical/high (must fix), N medium (should fix), N low (accepted)"

Ask the user after producing the model:
> "Would you like me to create GitHub Issues for the high-priority mitigations, or add them as TODOs to the relevant source files?"
