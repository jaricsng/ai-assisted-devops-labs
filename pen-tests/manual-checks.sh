#!/usr/bin/env bash
# =============================================================================
# Task Manager — Manual Penetration Test Checks
#
# AUTHORIZATION NOTICE: Run this script ONLY against your own running instance
# of the Task Manager application. Unauthorised testing of systems you do not
# own is illegal in most jurisdictions.
#
# Usage:
#   chmod +x pen-tests/manual-checks.sh
#   ./pen-tests/manual-checks.sh http://localhost:8000
#
# Each check prints PASS ✅ or FAIL ❌ with a description of the finding.
# =============================================================================

BASE_URL="${1:-http://localhost:8000}"
PASS=0
FAIL=0

_pass() { echo "  ✅  PASS — $1"; ((PASS++)); }
_fail() { echo "  ❌  FAIL — $1"; ((FAIL++)); }
_info() { echo ""; echo "── $1 ──────────────────────────────────────────"; }

echo ""
echo "Task Manager Penetration Test — Manual Checks"
echo "Target: $BASE_URL"
echo "================================================================="

# ─── A01: Broken Access Control ──────────────────────────────────────────────
_info "A01 — Broken Access Control"

# Create two users
EMAIL_A="pentest_a_$(date +%s)@example.com"
EMAIL_B="pentest_b_$(date +%s)@example.com"

curl -sf -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL_A\",\"full_name\":\"User A\",\"password\":\"PenTest123!\"}" > /dev/null

curl -sf -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL_B\",\"full_name\":\"User B\",\"password\":\"PenTest123!\"}" > /dev/null

TOKEN_A=$(curl -sf -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL_A\",\"password\":\"PenTest123!\"}" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)

TOKEN_B=$(curl -sf -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL_B\",\"password\":\"PenTest123!\"}" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)

# User A creates a project
PROJECT_A=$(curl -sf -X POST "$BASE_URL/projects" \
  -H "Authorization: Bearer $TOKEN_A" -H "Content-Type: application/json" \
  -d '{"name":"User A Private Project"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null)

# IDOR check: User B tries to access User A's project
if [ -n "$PROJECT_A" ]; then
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $TOKEN_B" \
    "$BASE_URL/projects/$PROJECT_A")
  if [ "$STATUS" = "403" ] || [ "$STATUS" = "404" ]; then
    _pass "IDOR: User B cannot read User A's project (HTTP $STATUS)"
  else
    _fail "IDOR: User B received HTTP $STATUS on User A's project — potential data leak"
  fi
fi

# User A creates a task
TASK_A=$(curl -sf -X POST "$BASE_URL/projects/$PROJECT_A/tasks" \
  -H "Authorization: Bearer $TOKEN_A" -H "Content-Type: application/json" \
  -d '{"title":"Secret Task","priority":"HIGH"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null)

# IDOR: User B tries to update User A's task
if [ -n "$TASK_A" ]; then
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH \
    "$BASE_URL/projects/$PROJECT_A/tasks/$TASK_A" \
    -H "Authorization: Bearer $TOKEN_B" -H "Content-Type: application/json" \
    -d '{"status":"IN_PROGRESS"}')
  if [ "$STATUS" = "403" ] || [ "$STATUS" = "404" ]; then
    _pass "IDOR: User B cannot modify User A's task (HTTP $STATUS)"
  else
    _fail "IDOR: User B received HTTP $STATUS when modifying User A's task — privilege escalation"
  fi
fi

# Unauthenticated access to protected resource
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/projects")
if [ "$STATUS" = "401" ] || [ "$STATUS" = "403" ]; then
  _pass "Unauthenticated request to /projects returns HTTP $STATUS"
else
  _fail "Unauthenticated request to /projects returned HTTP $STATUS (expected 401)"
fi

# ─── A02: Cryptographic Failures ─────────────────────────────────────────────
_info "A02 — Cryptographic Failures"

# JWT with 'none' algorithm (alg:none attack)
NONE_TOKEN="eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiIxIn0."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $NONE_TOKEN" "$BASE_URL/projects")
if [ "$STATUS" = "401" ] || [ "$STATUS" = "403" ]; then
  _pass "JWT alg:none rejected (HTTP $STATUS)"
else
  _fail "JWT alg:none accepted — critical authentication bypass vulnerability"
fi

# Tampered JWT (valid structure, invalid signature)
TAMPERED="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI5OTk5OTkifQ.INVALIDSIGNATURE"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $TAMPERED" "$BASE_URL/projects")
if [ "$STATUS" = "401" ] || [ "$STATUS" = "403" ]; then
  _pass "Tampered JWT signature rejected (HTTP $STATUS)"
else
  _fail "Tampered JWT accepted — JWT signature validation is broken"
fi

# Expired token simulation (can't easily create one without the secret — just note it)
echo "  ℹ️   NOTE: Test token expiry manually by waiting past access_token_expire_minutes"
echo "       or temporarily setting ACCESS_TOKEN_EXPIRE_MINUTES=0 and retrying a request"

# ─── A03: Injection ───────────────────────────────────────────────────────────
_info "A03 — Injection"

if [ -z "$TOKEN_A" ] || [ -z "$PROJECT_A" ]; then
  echo "  ⚠️   SKIP — A01 setup did not complete (rate limiting or registration failed)."
  echo "       Wait 60 s after a previous run and retry, or use a fresh IP address."
else
  # SQL injection probe in task title
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    "$BASE_URL/projects/$PROJECT_A/tasks" \
    -H "Authorization: Bearer $TOKEN_A" -H "Content-Type: application/json" \
    -d "{\"title\":\"'; DROP TABLE tasks; --\",\"priority\":\"LOW\"}")
  if [ "$STATUS" = "201" ] || [ "$STATUS" = "422" ]; then
    # 201 = stored safely; 422 = rejected by validation; both acceptable
    # A 500 would indicate the SQL was executed
    _pass "SQL injection in task title: HTTP $STATUS (payload treated as data, not SQL)"
  else
    _fail "SQL injection probe returned HTTP $STATUS — investigate server logs for errors"
  fi

  # XSS probe in project name
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    "$BASE_URL/projects" \
    -H "Authorization: Bearer $TOKEN_A" -H "Content-Type: application/json" \
    -d '{"name":"<script>alert(1)</script>"}')
  if [ "$STATUS" = "201" ] || [ "$STATUS" = "422" ]; then
    _pass "XSS payload in project name: HTTP $STATUS (stored/rejected safely — API returns JSON, not HTML)"
  else
    _fail "XSS probe returned HTTP $STATUS — investigate"
  fi
fi

# ─── A04: Insecure Design ────────────────────────────────────────────────────
_info "A04 — Insecure Design"

# Status transition bypass: attempt TODO → DONE (skipping intermediate states)
TASK_B=$(curl -sf -X POST "$BASE_URL/projects/$PROJECT_A/tasks" \
  -H "Authorization: Bearer $TOKEN_A" -H "Content-Type: application/json" \
  -d '{"title":"Transition Test","priority":"MEDIUM"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null)

if [ -n "$TASK_B" ]; then
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH \
    "$BASE_URL/projects/$PROJECT_A/tasks/$TASK_B" \
    -H "Authorization: Bearer $TOKEN_A" -H "Content-Type: application/json" \
    -d '{"status":"DONE"}')
  if [ "$STATUS" = "422" ]; then
    _pass "Business rule enforced: TODO→DONE rejected with 422"
  else
    _fail "Business rule bypass: TODO→DONE returned HTTP $STATUS (expected 422)"
  fi
fi

# Rate limiting check: 20 rapid login attempts
echo "  ⏱️   Testing login rate limiting (20 rapid requests)..."
FAIL_COUNT=0
for i in $(seq 1 20); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"nonexistent$i@example.com\",\"password\":\"wrong\"}")
  if [ "$STATUS" = "429" ]; then
    _pass "Rate limiting active: received 429 after $i requests"
    FAIL_COUNT=-1  # signal that rate limiting was found
    break
  fi
done
if [ "$FAIL_COUNT" = "0" ]; then
  _fail "No rate limiting on /auth/login — 20 consecutive failed logins all returned 200/401 without throttling"
fi

# User enumeration: does login distinguish "email not found" vs "wrong password"?
RESP_EXIST=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL_A\",\"password\":\"wrongpassword\"}" 2>/dev/null)
RESP_NOEXIST=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"definitelynotreal@example.com","password":"wrongpassword"}' 2>/dev/null)
if [ "$RESP_EXIST" = "$RESP_NOEXIST" ]; then
  _pass "Login error responses are identical (no user enumeration)"
else
  _fail "Login responses differ for existing vs non-existing email — user enumeration possible"
  echo "       Existing user response:     $(echo $RESP_EXIST | python3 -m json.tool 2>/dev/null | head -3)"
  echo "       Non-existing user response: $(echo $RESP_NOEXIST | python3 -m json.tool 2>/dev/null | head -3)"
fi

# ─── A05: Security Misconfiguration ─────────────────────────────────────────
_info "A05 — Security Misconfiguration"

# Check CORS headers
CORS=$(curl -sI -X OPTIONS "$BASE_URL/projects" \
  -H "Origin: https://evil.example.com" \
  -H "Access-Control-Request-Method: GET" | grep -i "access-control-allow-origin")
if echo "$CORS" | grep -q "evil.example.com\|\*"; then
  _fail "CORS: API allows requests from evil.example.com or wildcard origin — check allow_origins"
else
  _pass "CORS: API does not reflect arbitrary origins"
fi

# Check for server version disclosure in headers
SERVER=$(curl -sI "$BASE_URL/health" | grep -i "^server:")
if echo "$SERVER" | grep -qiE "uvicorn|fastapi|python|version"; then
  _fail "Server header discloses technology: $SERVER"
else
  _pass "Server header does not disclose technology versions"
fi

# ─── A07: Auth Failures ──────────────────────────────────────────────────────
_info "A07 — Identification and Authentication Failures"

# Weak password accepted?
WEAK_EMAIL="weakpass_$(date +%s)@example.com"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$WEAK_EMAIL\",\"full_name\":\"Weak\",\"password\":\"123\"}")
if [ "$STATUS" = "422" ]; then
  _pass "Weak password '123' rejected with 422"
else
  _fail "Weak password '123' accepted (HTTP $STATUS) — no minimum password length enforced"
fi

# Empty password
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"empty_$(date +%s)@example.com\",\"full_name\":\"Empty\",\"password\":\"\"}")
if [ "$STATUS" = "422" ]; then
  _pass "Empty password rejected with 422"
else
  _fail "Empty password accepted (HTTP $STATUS)"
fi

# ─── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo "================================================================="
echo "  Pen Test Summary"
echo "  PASS: $PASS   FAIL: $FAIL"
echo "================================================================="
echo ""
if [ "$FAIL" -gt 0 ]; then
  echo "  ❌  $FAIL check(s) failed. Review the findings above and either"
  echo "      fix the vulnerability or document the accepted risk in docs/adr/."
  exit 1
else
  echo "  ✅  All manual checks passed."
  exit 0
fi
