"""Locust load test scenarios for the Task Manager API.

Usage:
    locust -f locustfile.py --host http://localhost:8000
    locust -f locustfile.py --host http://localhost:8000 --headless -u 50 -r 5 -t 5m

Users:
    ReadHeavyUser  — browses projects and task boards (60% of traffic)
    TaskWriterUser — creates projects, tasks, moves statuses (30% of traffic)
    AuthStressUser — exercises login/register paths (10% of traffic)
"""
import random
import time
from locust import HttpUser, TaskSet, between, events, task

# ── Helpers ───────────────────────────────────────────────────────────────────

def _unique_email() -> str:
    return f"user_{time.time_ns()}_{random.randint(1000, 9999)}@loadtest.local"


def _register_and_login(client) -> str | None:
    """Register a new user and return the JWT access token, or None on failure."""
    email = _unique_email()
    reg = client.post(
        "/auth/register",
        json={"email": email, "full_name": "Load Tester", "password": "LoadTest123!"},
        name="/auth/register",
    )
    if reg.status_code != 201:
        return None

    login = client.post(
        "/auth/login",
        json={"email": email, "password": "LoadTest123!"},
        name="/auth/login",
    )
    if login.status_code != 200:
        return None

    return login.json().get("access_token")


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Task Sets ─────────────────────────────────────────────────────────────────

class BrowseTasks(TaskSet):
    """Read-heavy scenario: list projects and inspect task boards."""

    def on_start(self):
        self.token = _register_and_login(self.client)
        if not self.token:
            self.interrupt()
        # Create one project to browse
        r = self.client.post(
            "/projects",
            json={"name": f"Load Project {time.time_ns()}"},
            headers=_auth_headers(self.token),
            name="/projects [POST]",
        )
        if r.status_code == 201:
            self.project_id = r.json()["id"]
            # Seed a few tasks
            for i in range(3):
                self.client.post(
                    f"/projects/{self.project_id}/tasks",
                    json={"title": f"Task {i}", "priority": random.choice(["LOW", "MEDIUM", "HIGH"])},
                    headers=_auth_headers(self.token),
                    name="/projects/{id}/tasks [POST]",
                )
        else:
            self.project_id = None

    @task(5)
    def list_projects(self):
        self.client.get(
            "/projects",
            headers=_auth_headers(self.token),
            name="/projects [GET]",
        )

    @task(8)
    def list_tasks(self):
        if self.project_id:
            self.client.get(
                f"/projects/{self.project_id}/tasks",
                headers=_auth_headers(self.token),
                name="/projects/{id}/tasks [GET]",
            )

    @task(2)
    def health_check(self):
        self.client.get("/health", name="/health")

    @task(1)
    def ready_check(self):
        self.client.get("/ready", name="/ready")


class CreateAndManageTasks(TaskSet):
    """Write-heavy scenario: create projects, tasks, and move statuses."""

    def on_start(self):
        self.token = _register_and_login(self.client)
        if not self.token:
            self.interrupt()
        self.project_id = None
        self.task_ids = []  # (task_id, current_status)

    @task(2)
    def create_project(self):
        r = self.client.post(
            "/projects",
            json={"name": f"Project {time.time_ns()}"},
            headers=_auth_headers(self.token),
            name="/projects [POST]",
        )
        if r.status_code == 201:
            self.project_id = r.json()["id"]

    @task(5)
    def create_task(self):
        if not self.project_id:
            return
        r = self.client.post(
            f"/projects/{self.project_id}/tasks",
            json={
                "title": f"Task {time.time_ns()}",
                "priority": random.choice(["LOW", "MEDIUM", "HIGH"]),
            },
            headers=_auth_headers(self.token),
            name="/projects/{id}/tasks [POST]",
        )
        if r.status_code == 201:
            self.task_ids.append((r.json()["id"], "TODO"))

    @task(6)
    def advance_task_status(self):
        if not self.task_ids or not self.project_id:
            return
        # Pick a random in-progress task
        idx = random.randrange(len(self.task_ids))
        task_id, status = self.task_ids[idx]

        # Only advance along the valid path; skip terminal states
        next_status = {
            "TODO": "IN_PROGRESS",
            "IN_PROGRESS": "IN_REVIEW",
            "IN_REVIEW": "DONE",
        }.get(status)

        if not next_status:
            return  # terminal state — nothing to do

        r = self.client.patch(
            f"/projects/{self.project_id}/tasks/{task_id}",
            json={"status": next_status},
            headers=_auth_headers(self.token),
            name="/projects/{id}/tasks/{id} [PATCH]",
        )
        if r.status_code == 200:
            self.task_ids[idx] = (task_id, next_status)

    @task(3)
    def add_comment(self):
        if not self.task_ids or not self.project_id:
            return
        task_id, _ = random.choice(self.task_ids)
        self.client.post(
            f"/projects/{self.project_id}/tasks/{task_id}/comments",
            json={"body": "Load test comment"},
            headers=_auth_headers(self.token),
            name="/tasks/{id}/comments [POST]",
        )


# ── User Classes ──────────────────────────────────────────────────────────────

class ReadHeavyUser(HttpUser):
    """Simulates a team member who mostly browses the Kanban board."""
    tasks = [BrowseTasks]
    wait_time = between(1, 3)
    weight = 6


class TaskWriterUser(HttpUser):
    """Simulates a team member who actively creates and manages tasks."""
    tasks = [CreateAndManageTasks]
    wait_time = between(2, 5)
    weight = 3


class AuthStressUser(HttpUser):
    """Exercises the auth endpoints directly (login/register churn)."""
    wait_time = between(0.5, 2)
    weight = 1

    @task
    def register_and_login(self):
        _register_and_login(self.client)


# ── Event hooks (summary stats) ───────────────────────────────────────────────

@events.quitting.add_listener
def on_quitting(environment, **kwargs):
    stats = environment.stats
    total = stats.total
    print(f"\n{'='*60}")
    print(f"  Load Test Summary")
    print(f"{'='*60}")
    print(f"  Total requests : {total.num_requests}")
    print(f"  Failures       : {total.num_failures} ({100*total.fail_ratio:.1f}%)")
    print(f"  Median (p50)   : {total.median_response_time} ms")
    print(f"  95th pct (p95) : {total.get_response_time_percentile(0.95)} ms")
    print(f"  99th pct (p99) : {total.get_response_time_percentile(0.99)} ms")
    print(f"  RPS            : {total.current_rps:.1f}")
    print(f"{'='*60}\n")
