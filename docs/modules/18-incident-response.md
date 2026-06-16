# Module 18 — Incident Response & On-Call Engineering

## Learning Objectives

- Classify incidents by severity (P1–P4) and understand why classification drives urgency
- Describe the roles in an incident: commander, responder, communicator, scribe
- Write a runbook that an on-call engineer can follow at 3 AM with no context
- Use structured logs and distributed traces to diagnose a production failure in under 15 minutes
- Conduct a blameless post-mortem and extract action items that prevent recurrence
- Use Claude Code to accelerate incident diagnosis and generate runbook drafts
- Wire the Task Manager's existing alerts, logs, and traces into a coherent incident workflow

---

## Background

### What is an incident?

An incident is any unplanned event that degrades or disrupts service. A slow database query is an incident. A deploy that caused a surge in 5xx errors is an incident. An incident does not require total outage — degraded performance counts.

### Incident lifecycle

```
Detection → Triage → Escalation → Mitigation → Resolution → Post-mortem
```

**Detection** comes from monitoring (Grafana/Prometheus alerts, Blackbox probes, customer reports).  
**Triage** is the first 5 minutes: *how bad is this, who is affected, what changed?*  
**Escalation** happens when triage cannot resolve within a defined SLA.  
**Mitigation** stops the bleeding — a rollback, a restart, an emergency config change.  
**Resolution** fully restores service and removes the workaround.  
**Post-mortem** captures the root cause and action items within 48 hours.

### Severity classification

| Severity | Impact | Response SLA | Example |
|----------|--------|-------------|---------|
| **P1 — Critical** | Full outage, all users affected | Respond in 5 min, escalate in 15 min | API down, DB unreachable |
| **P2 — High** | Core feature broken | Respond in 15 min, escalate in 30 min | Login failing for all users |
| **P3 — Medium** | Feature degraded, workaround exists | Next business hour | Task creation returning 429 intermittently |
| **P4 — Low** | Cosmetic or minor | Next sprint | Stale metric label in Grafana |

### Roles during an incident

| Role | Responsibility |
|------|---------------|
| **Incident Commander (IC)** | Owns the incident end-to-end; makes decisions; tracks action items |
| **Primary Responder** | Investigates and implements fixes |
| **Communicator** | Updates stakeholders; maintains the incident timeline |
| **Scribe** | Records every action taken, every hypothesis tested, and the timeline |

For a small team one person can fill multiple roles, but the IC must stay separate from the primary responder — firefighting and commanding require different focus.

### Why blameless post-mortems?

Blame causes engineers to hide incidents and workarounds. A blameless culture acknowledges that systems fail, humans operate in imperfect environments, and the goal is to improve the system — not to punish the person who happened to be deploying when the failure occurred.

---

## Prerequisites

The full observability stack must be running:

```bash
docker compose --profile observability up -d
```

The API must be running with OTel enabled (`OTEL_ENABLED=true`) and the alerting rules from Module 15 loaded. Verify:

```bash
curl -s http://localhost:9090/api/v1/alerts \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['data']['alerts']), 'alerts loaded')"
```

---

## Activities

### 1. Map your alert landscape

Before writing runbooks, inventory what alerts are already configured and what they mean operationally.

```bash
# List all alert rules currently loaded in Prometheus
curl -s http://localhost:9090/api/v1/rules \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for group in data['data']['groups']:
    for rule in group['rules']:
        if rule['type'] == 'alerting':
            print(f\"{rule['name']:40s} severity={rule['labels'].get('severity','?')}\")
"
```

You should see the four alerts from `observability/grafana/provisioning/alerting/rules.yaml`:
- `HighErrorRate` (critical)
- `HighLatency` (warning)
- `DatabaseUnreachable` (critical)
- `HighRejectionRate` (warning)

Ask Claude Code:
> "Look at `observability/grafana/provisioning/alerting/rules.yaml` and `docs/runbooks/disaster-recovery.md`. For each alert, identify which section of the disaster recovery runbook provides the remediation steps. Are there any alerts without runbook coverage? If so, what incident scenarios are we missing?"

---

### 2. Write a runbook for each critical alert

A good runbook has three sections: **Triage**, **Remediation**, **Escalation**. Each step is an action — not a question.

Create `docs/runbooks/runbook-database-unreachable.md`:

```markdown
# Runbook — DatabaseUnreachable

**Alert:** DatabaseUnreachable  
**Severity:** Critical (P1)  
**SLO impact:** Service fully unavailable — readiness probe failing  
**Trigger:** `probe_success{job="readiness"} == 0` for 1 minute

---

## Triage (< 5 minutes)

**Goal: determine whether the DB container is down, overloaded, or unreachable from the API.**

1. Check API health:
   ```bash
   curl -sf http://localhost:8000/health && echo "API process: UP" || echo "API process: DOWN"
   curl -sf http://localhost:8000/ready && echo "DB: REACHABLE" || echo "DB: UNREACHABLE"
   ```

2. Check DB container:
   ```bash
   docker compose ps db
   docker compose logs --tail=20 db
   ```

3. Test direct DB connectivity (bypasses the API):
   ```bash
   docker compose exec db pg_isready -U taskuser -d taskmanager
   ```

4. Check API logs for the exact error:
   ```bash
   docker compose logs --tail=30 api | grep -i "error\|exception\|db\|postgres"
   ```

---

## Remediation

### If DB container is stopped:
```bash
docker compose up -d db
# Wait for healthy
docker compose exec db pg_isready -U taskuser -d taskmanager
docker compose restart api
```

### If DB is up but API can't connect (pool exhaustion):
```bash
# Check connection count
docker compose exec db psql -U taskuser -d taskmanager \
  -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"
# Restart API to flush stale pool connections
docker compose restart api
```

### If DB disk is full:
```bash
docker compose exec db psql -U taskuser -d taskmanager \
  -c "SELECT pg_size_pretty(pg_database_size('taskmanager'));"
# Free space or expand volume before restarting
```

### If schema migration is blocking (lock contention):
```bash
docker compose exec db psql -U taskuser -d taskmanager \
  -c "SELECT pid, query, state, wait_event_type, wait_event FROM pg_stat_activity WHERE wait_event IS NOT NULL;"
# Terminate blocking query if safe:
# SELECT pg_terminate_backend(<pid>);
```

---

## Verify resolution
```bash
curl -sf http://localhost:8000/ready && echo "RESOLVED"
# Monitor the Prometheus DatabaseUnreachable alert — it should leave 'firing' within 2 minutes
```

---

## Escalation

If not resolved in 15 minutes:
1. Post to `#incidents`: alert name, time firing, steps taken, current hypothesis
2. Escalate to the DB team / infrastructure owner
3. Check if a deploy preceded the alert (GitHub Actions → recent runs)

---

## Post-incident

See post-mortem template in `docs/runbooks/disaster-recovery.md` §7.  
SLO impact: calculate minutes of `probe_success == 0` × (1/total_minutes_in_month) for the availability SLO.
```

Ask Claude Code:
> "Review this runbook. What questions would an on-call engineer realistically ask at 3 AM that this runbook doesn't answer? Suggest one specific addition for each gap."

---

### 3. Write a runbook for the HighRejectionRate alert

Create `docs/runbooks/runbook-high-rejection-rate.md`. This alert fires when `POST /auth/login` is being rate-limited at > 50 req/s — a potential brute-force or credential-stuffing attack.

```markdown
# Runbook — HighRejectionRate

**Alert:** HighRejectionRate  
**Severity:** Warning (P3 by default; escalate to P2 if IPs are new/unexpected)  
**Trigger:** `sum(rate(http_server_duration_milliseconds_count{http_status_code="429"}[1m])) > 50`

## Triage

1. Confirm alert is real (not a pen-test run):
   ```bash
   docker compose logs api --since=5m | grep '"status_code":429' | head -20
   ```

2. Identify the source IP (if X-Forwarded-For is set by your reverse proxy):
   ```bash
   docker compose logs api --since=5m | grep '"status_code":429' \
     | python3 -c "import sys,json; [print(json.loads(l).get('client_host','?')) for l in sys.stdin if l.strip()]" \
     | sort | uniq -c | sort -rn | head
   ```

3. Determine if this is a scheduled test run:
   - Is a pen test running? (`./pen-tests/manual-checks.sh` fires 10+ login attempts)
   - Is an E2E test running? (`npx playwright test`)

## Remediation

### If a pen test exhausted the rate-limit bucket:
```bash
docker compose restart api   # clears the in-memory bucket
```
Then re-run E2E tests.

### If this is a real attack:
1. Block the IP at the network/proxy level (WAF, nginx `deny` directive)
2. Check if any accounts were successfully compromised during the burst:
   ```bash
   docker compose logs api --since=60m | grep '"action":"LOGIN_SUCCESS"' | head -20
   ```
3. If accounts were compromised: force-expire all tokens by restarting the API (clears in-memory JTI set)

## Post-incident
Document the source IP, volume, and whether any logins succeeded. If this repeats, consider:
- Adding IP-based blocking in a WAF or nginx upstream
- Adding CAPTCHA to the login endpoint
- Migrating the rate-limiter bucket to Redis for persistence across restarts
```

Ask Claude Code:
> "The current `RateLimitMiddleware` uses an in-memory deque keyed by IP. If an attacker uses 100 different IPs (a botnet), the rate limiter will not help. What three architectural changes would address this? Rank them by implementation complexity."

---

### 4. Simulate a P1 incident and run your runbook

Stop the database to trigger the `DatabaseUnreachable` alert:

```bash
docker compose stop db
```

Immediately:
1. Watch Grafana: http://localhost:3000 → Alerting → Alert rules
2. Watch Prometheus: http://localhost:9090/alerts
3. Open your `runbook-database-unreachable.md` and follow step by step

Record the time from:
- DB stopped → alert fires (should be ~1 minute)
- Alert fires → you identify the root cause via the runbook
- Root cause identified → DB restarted and `/ready` returns 200

Restart the DB when done:

```bash
docker compose start db
docker compose restart api
curl -sf http://localhost:8000/ready && echo "Resolved"
```

Ask Claude Code:
> "I just simulated a DatabaseUnreachable incident. Walk me through what a post-mortem document would look like for this event. Fill in the timeline section with realistic timestamps, the root cause, and at least two action items — one technical and one process."

---

### 5. Write a blameless post-mortem

Create `docs/post-mortems/2026-06-15-db-container-stop.md` using the incident you just simulated:

```markdown
# Post-Mortem: Database Container Stopped — 2026-06-15

**Severity:** P1  
**Duration:** ~5 minutes  
**Impact:** Full service outage — all API requests returning 503 for the duration  
**Author:** [your name]  
**Status:** Resolved / Action items open

## Timeline (UTC)

| Time | Event |
|------|-------|
| HH:MM | `docker compose stop db` issued |
| HH:MM | `/ready` first returned 503 |
| HH:MM | `DatabaseUnreachable` alert entered `firing` state in Prometheus |
| HH:MM | On-call (self) opened runbook |
| HH:MM | Root cause identified: DB container stopped |
| HH:MM | `docker compose start db && docker compose restart api` issued |
| HH:MM | `/ready` returned 200; alert cleared |

## Root Cause

The PostgreSQL container was stopped manually as part of a controlled incident simulation. In production, the equivalent scenario would be an OOM-killed DB container, a failed volume mount, or an unintended `docker stop` during maintenance.

## Contributing Factors

- The API's connection pool holds open connections; when the DB restarts the pool contains stale connections that must be recycled, adding 5–10 seconds of 503 errors even after the DB is healthy.
- The rate at which the alert fires (1-minute `for:` clause) means 1 minute of unavailability is guaranteed before anyone is notified.

## What Went Well

- The alert fired promptly and the runbook steps were clear.
- `pg_isready` correctly distinguished "DB container down" from "DB up, connection pool exhausted".

## What Went Wrong

- The runbook did not include the step to verify pool recycling after DB restart — the API continued to return sporadic errors for 30 seconds after the DB came back.

## Action Items

| Action | Owner | Due | Status |
|--------|-------|-----|--------|
| Add pool recycling check to `runbook-database-unreachable.md` | [you] | next session | Open |
| Add `pool_pre_ping=True` to SQLAlchemy engine config (already present in solution) | — | Done | Closed |
| Review whether the 1-minute `for:` clause on `DatabaseUnreachable` is too slow | [you] | next session | Open |
```

Ask Claude Code:
> "Review this post-mortem draft. Apply the Google SRE post-mortem principles: Is it blameless? Does the root cause identify the systemic condition (not just the immediate trigger)? Is each action item SMART (Specific, Measurable, Achievable, Relevant, Time-bound)? Suggest specific improvements."

---

### 6. Add on-call documentation

Create `docs/runbooks/on-call-guide.md` describing who is responsible and how to respond:

```markdown
# On-Call Guide — Task Manager

## Who is on call?

For this lab: you. In production, on-call is assigned via a rotation in your incident management tool (PagerDuty, OpsGenie, Grafana OnCall, etc.).

## How to know an alert fired

Grafana can send alerts via email, Slack, PagerDuty, or webhook. For local dev:

- Grafana UI: http://localhost:3000 → Alerting → Alert rules (shows firing state)
- Prometheus UI: http://localhost:9090/alerts
- API logs: `docker compose logs -f api | grep '"level":"error"'`

## First 5 minutes checklist

- [ ] Open Grafana — which alert is firing, for how long?
- [ ] Check `/health` and `/ready`
- [ ] Check recent deployments (GitHub Actions → last 10 runs)
- [ ] Open the relevant runbook from `docs/runbooks/`
- [ ] Post to `#incidents`: "Investigating [alert name] at [time]. Update in 15 minutes."

## Escalation contacts

| When | Who | How |
|------|-----|-----|
| P1 not resolved in 15 min | Engineering lead | Slack DM + phone |
| P1 not resolved in 30 min | CTO / VP Engineering | Phone |
| Security incident (data breach suspected) | Security team | Dedicated security channel |

## After resolving

- [ ] Write a post-mortem in `docs/post-mortems/YYYY-MM-DD-<title>.md` (within 48 hours for P1/P2)
- [ ] Update the runbook with anything that wasn't in it
- [ ] Close the incident in your tracking tool
- [ ] Post resolution to `#incidents`
```

---

## Checkpoint

- [ ] `docs/runbooks/runbook-database-unreachable.md` written and followed during the live simulation
- [ ] `docs/runbooks/runbook-high-rejection-rate.md` written
- [ ] `docs/runbooks/runbook-high-error-rate.md` written
- [ ] `docs/runbooks/on-call-guide.md` written with escalation contacts filled in
- [ ] `docs/post-mortems/template.md` created from the standard template
- [ ] `docs/post-mortems/2026-06-15-db-container-stop.md` written with timeline, root cause, and action items
- [ ] Simulated P1 incident: DB stopped, alert fired, runbook followed, DB restarted, `/ready` returned 200
- [ ] Commit: `docs(ops): add incident runbooks, on-call guide, and post-mortem template`

> **Reference implementations** for all checklist items above are in the project repo. Compare your versions against:
> - `docs/runbooks/runbook-database-unreachable.md`
> - `docs/runbooks/runbook-high-error-rate.md`
> - `docs/runbooks/runbook-high-rejection-rate.md`
> - `docs/runbooks/on-call-guide.md`
> - `docs/post-mortems/template.md`
> - `docs/post-mortems/2026-06-15-db-container-stop.md`

---

## Troubleshooting

| Problem | Likely cause | Fix |
|---------|-------------|-----|
| `DatabaseUnreachable` alert not firing after `docker compose stop db` | Observability profile not running or alert rules not loaded | `docker compose --profile observability up -d && docker compose restart prometheus` |
| Alert fires immediately (before 1 minute) | `for:` clause missing or set to 0s | Check `rules.yaml` — `DatabaseUnreachable` uses `for: 1m` |
| Logs show no 503s despite DB being down | `OTEL_ENABLED=false` — structured logging still works, check `docker compose logs api` | Structured logging is separate from OTel; logs should show `readiness_check_failed` |
| Post-mortem action items keep getting lost | No tracking system | Link action items to GitHub Issues (`Fixes #N`) so they appear in the project board |

---

## Going Further

- **Chaos engineering:** Use [Chaos Monkey](https://github.com/Netflix/chaosmonkey) or [Pumba](https://github.com/alexei-led/pumba) to inject random container failures and test your runbooks under realistic conditions.
- **Game days:** Schedule quarterly "game day" exercises where the team intentionally breaks the system and practices the incident response procedure.
- **Incident tracking:** Integrate with an incident management tool (PagerDuty, OpsGenie, Grafana OnCall) to automate alerting, rotation, and post-mortem tracking.
- **SLO impact:** After each P1/P2 incident, calculate the minutes of availability SLO consumed. Report this in the engineering team's monthly review.
