# Post-Mortem Template

> Copy this file to `docs/post-mortems/YYYY-MM-DD-<slug>.md` and fill in each section.
> Complete within 48 hours of incident resolution.

---

## Incident Summary

| Field | Value |
|-------|-------|
| **Date** | YYYY-MM-DD |
| **Duration** | HH:MM – HH:MM (N minutes) |
| **Severity** | P1 / P2 / P3 |
| **Impact** | Brief description of user-visible impact |
| **Root cause** | One-sentence summary |
| **Author** | @handle |
| **Reviewers** | @handle, @handle |

---

## Timeline

All times in UTC.

| Time | Event |
|------|-------|
| HH:MM | Alert fired / incident detected |
| HH:MM | On-call acknowledged |
| HH:MM | Initial triage complete |
| HH:MM | Root cause identified |
| HH:MM | Fix deployed / mitigation applied |
| HH:MM | Service confirmed recovered |
| HH:MM | Incident closed |

---

## Impact

- **Users affected:** N (estimated)
- **Requests failed:** N (from Prometheus / logs)
- **Data loss:** None / describe if any
- **SLO breach:** Yes/No — error rate reached X%, p95 latency reached Xms

---

## Root Cause

Describe the technical root cause in 2–4 sentences. Include:
- What failed
- Why it failed
- Why the failure propagated (contributing factors)

---

## Contributing Factors

- Factor 1 (e.g. missing alert on DB disk usage)
- Factor 2 (e.g. retry without backoff amplified load)

---

## Detection

How was the incident detected? (Alert fired / user report / manual check)

Could it have been detected sooner? If yes, what monitoring is missing?

---

## Resolution

What steps resolved the incident? Reference the runbook section used.

---

## Action Items

| # | Action | Owner | Due date | Priority |
|---|--------|-------|----------|----------|
| 1 | Fix root cause | @handle | YYYY-MM-DD | P1 |
| 2 | Add missing alert | @handle | YYYY-MM-DD | P2 |
| 3 | Update runbook | @handle | YYYY-MM-DD | P3 |

---

## Lessons Learned

What went well? What could be improved? What surprised the team?

---

## References

- Relevant Jaeger traces: (link or trace IDs)
- Grafana snapshot: (link)
- Related tickets: (link)
