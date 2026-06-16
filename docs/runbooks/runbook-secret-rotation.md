# Runbook — Secret Rotation

**When to run:** Quarterly schedule, after a suspected credential leak, or after an engineer with production access leaves the team.  
**Severity:** P2 (planned maintenance) → P1 (emergency rotation after a breach)  
**Estimated duration:** 45–60 minutes for a planned rotation; 15 minutes for emergency rotation  
**On-call channel:** #task-manager-oncall

---

## 1. What needs rotating and when

| Secret | Rotation trigger | Impact if not rotated |
|--------|-----------------|----------------------|
| `SECRET_KEY` (JWT signing key) | Quarterly; any suspected leak; engineer offboarding | All existing sessions remain valid indefinitely |
| `DATABASE_URL` (PostgreSQL password) | Annual; any suspected DB compromise | Attacker retains DB access |
| `GHCR_TOKEN` / registry credentials | Per GitHub's recommendation; any suspected leak | Attacker can push malicious images |

---

## 2. Rotate `SECRET_KEY` (JWT signing key) without downtime

The JWT signing key invalidates all sessions when changed. Rotating it abruptly logs out every user. Use a **dual-key window** to rotate gracefully.

### Step 1 — Generate the new key

```bash
NEW_KEY=$(openssl rand -hex 32)
echo "New key: $NEW_KEY"
# Store this securely — do NOT commit it
```

### Step 2 — Deploy with both old and new key accepted

Modify `backend/app/config.py` to accept a `SECRET_KEY_PREVIOUS` env var and try both keys on JWT decode. Deploy this version first.

```python
# Temporary dual-key decode in auth_service.py
def get_token_payload(token: str) -> dict:
    for key in [settings.secret_key, settings.secret_key_previous]:
        if not key:
            continue
        try:
            return jwt.decode(token, key, algorithms=["HS256"])
        except Exception:
            continue
    raise HTTPException(status_code=401, detail="Invalid token")
```

Set both secrets in your environment / GitHub Secrets:
```bash
SECRET_KEY=<new-key>
SECRET_KEY_PREVIOUS=<old-key>
```

Deploy and verify both old and new tokens are accepted:
```bash
# Old token (issued before rotation) should still work
curl -H "Authorization: Bearer $OLD_TOKEN" http://localhost:8000/projects

# New login should use the new key
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test1234!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/projects
```

### Step 3 — Wait for token TTL expiry

Default JWT lifetime is 30 minutes. Wait at least 31 minutes after deploying the dual-key version so all old tokens expire naturally.

```bash
echo "Waiting for old tokens to expire (31 min)..."
sleep 1860
```

### Step 4 — Remove the old key

```bash
# Unset SECRET_KEY_PREVIOUS in your environment / GitHub Secrets
# Redeploy the API (no code change needed — just env var removal)
docker compose pull api && docker compose up -d api
```

Remove the dual-key decode logic from `auth_service.py` if you added it temporarily.

### Step 5 — Verify recovery

```bash
# Old token should now be rejected
curl -s -H "Authorization: Bearer $OLD_TOKEN" http://localhost:8000/projects
# Expected: HTTP 401

# New login should succeed
NEW_TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test1234!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
curl -H "Authorization: Bearer $NEW_TOKEN" http://localhost:8000/projects
# Expected: HTTP 200
```

---

## 3. Rotate the PostgreSQL password

### Step 1 — Set the new password in PostgreSQL

```bash
docker compose exec db psql -U taskuser -d taskmanager \
  -c "ALTER USER taskuser PASSWORD 'new-strong-password-here';"
```

### Step 2 — Update the DATABASE_URL secret

Update `DATABASE_URL` in GitHub Secrets / Secret Manager to use the new password:
```
postgresql+asyncpg://taskuser:new-strong-password-here@db:5432/taskmanager
```

### Step 3 — Redeploy the API

```bash
docker compose pull api && docker compose up -d api
```

### Step 4 — Verify

```bash
curl -sf http://localhost:8000/ready && echo "DB: OK"
# Expected: HTTP 200 — API successfully connected with the new password
```

---

## 4. Emergency rotation (suspected leak)

If credentials are suspected to have been compromised:

1. **Immediately** rotate both `SECRET_KEY` and `DATABASE_URL` using the steps above (skip the dual-key window — accept the user disruption)
2. Force-expire all active sessions by restarting the API (clears in-memory JTI set):
   ```bash
   docker compose restart api
   ```
3. Notify affected users to re-login and check their accounts for unauthorised activity
4. Review audit logs for unusual activity in the window before rotation:
   ```bash
   docker compose logs api --since=24h | grep -E '"action":"(LOGIN_SUCCESS|TASK_DELETED|PROJECT_DELETED)"'
   ```
5. File a security incident post-mortem using `docs/post-mortems/template.md`

---

## 5. Post-rotation checklist

- [ ] New `SECRET_KEY` stored in secrets manager (GitHub Secrets, Fly.io secrets, GCP Secret Manager) — NOT in `.env` or any committed file
- [ ] Old key removed from all environments
- [ ] `/ready` returns 200 after rotation
- [ ] New login flow verified end-to-end (login → use token → logout)
- [ ] Rotation date recorded in ops log (commit a dated note to `docs/operations.md` — not the key value)
- [ ] `SECRET_KEY_PREVIOUS` removed from environment if dual-key approach was used
- [ ] Post-mortem filed if this was an emergency rotation

---

## 6. Cloud-specific rotation

| Platform | Where secrets live | How to update |
|----------|--------------------|---------------|
| Fly.io | `flyctl secrets` | `flyctl secrets set SECRET_KEY=<new> --app task-manager-api` |
| Azure Container Apps | Azure Key Vault | Update secret version in Key Vault; ACA picks it up on next revision |
| AWS ECS | AWS Secrets Manager | Create new secret version; update task definition to reference the new ARN |
| GCP Cloud Run | GCP Secret Manager | `gcloud secrets versions add SECRET_KEY --data-file=<file>`; update Cloud Run to use `latest` |

See `docs/modules/17-infrastructure-as-code.md` for IaC-managed secret configuration.
