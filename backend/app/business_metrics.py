"""Domain-level Prometheus counters.

These counters are registered with prometheus_client and exposed via the
/metrics endpoint when OTEL_ENABLED=true (setup_telemetry mounts the ASGI
Prometheus app at /metrics).

Avoid high-cardinality labels (e.g. resource IDs) — they create one time
series per unique value and exhaust Prometheus storage.
"""

from prometheus_client import Counter

tasks_created_total = Counter(
    "tasks_created_total",
    "Total number of tasks successfully created",
)

projects_created_total = Counter(
    "projects_created_total",
    "Total number of projects successfully created",
)

task_status_transitions_total = Counter(
    "task_status_transitions_total",
    "Total number of task status transitions by direction",
    ["from_status", "to_status"],
)
