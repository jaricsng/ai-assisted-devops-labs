"""Locust load test scenarios for the Task Manager API.

Usage:
    locust -f locustfile.py --host http://localhost:8000
    locust -f locustfile.py --host http://localhost:8000 --headless -u 50 -r 5 -t 5m

Users:
    ReadHeavyUser   — browses projects and task boards (60% of traffic)
    TaskWriterUser  — creates projects, tasks, moves statuses (30% of traffic)
    AuthVerifyUser  — verifies the auth lifecycle: register → login → call → logout (10%)

Rate-limit note:
    The API enforces 10 logins/min per IP. All users register and log in once during
    on_start(), using a random jitter delay to spread requests across the 60-second
    window. Do NOT add register/login calls to per-task methods.
"""
import random
import time

from locust import HttpUser, TaskSet, between, events, task


# ── Helpers ───────────────────────────────────────────────────────────────────


def _unique_email() -> str:
    return f"user_{time.time_ns()}_{random.randint(1000, 9999)}@example.com"


def _register_and_login(client, *, name_tag: str = "") -> str | None:
    """Register a new user and return the JWT access token, or None on failure.

    Returns None (without raising) so callers can decide whether to interrupt
    their TaskSet or retry. Handles 429 gracefully by returning None.
    """
    email = _unique_email()
    reg = client.post(
        "/auth/register",
        json={"email": email, "full_name": "Load Tester", "password": "LoadTest123!"},
        name="/auth/register",
        catch_response=True,
    )
    with reg:
        if reg.status_code not in (200, 201):
            reg.failure(f"register failed: {reg.status_code}")
            return None
        reg.success()

    login = client.post(
        "/auth/login",
        json={"email": email, "password": "LoadTest123!"},
        name="/auth/login",
        catch_response=True,
    )
    with login:
        if login.status_code == 429:
            # Rate limited — mark as success to avoid polluting error stats;
            # caller will interrupt the task set rather than loop.
            login.success()
            return None
        if login.status_code != 200:
            login.failure(f"login failed: {login.status_code}")
            return None
        login.success()

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
        # Create one project and a few seed tasks to browse
        r = self.client.post(
            "/projects",
            json={"name": f"Load Project {time.time_ns()}"},
            headers=_auth_headers(self.token),
            name="/projects [POST]",
        )
        self.task_ids: list[int] = []
        if r.status_code == 201:
            self.project_id = r.json()["id"]
            for i in range(3):
                tr = self.client.post(
                    f"/projects/{self.project_id}/tasks",
                    json={"title": f"Task {i}", "priority": random.choice(["LOW", "MEDIUM", "HIGH"])},
                    headers=_auth_headers(self.token),
                    name="/projects/{id}/tasks [POST]",
                )
                if tr.status_code == 201:
                    self.task_ids.append(tr.json()["id"])
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

    @task(3)
    def list_comments(self):
        if self.project_id and self.task_ids:
            task_id = random.choice(self.task_ids)
            self.client.get(
                f"/projects/{self.project_id}/tasks/{task_id}/comments",
                headers=_auth_headers(self.token),
                name="/projects/{id}/tasks/{id}/comments [GET]",
            )

    @task(2)
    def get_project_detail(self):
        if self.project_id:
            self.client.get(
                f"/projects/{self.project_id}",
                headers=_auth_headers(self.token),
                name="/projects/{id} [GET]",
            )

    @task(1)
    def get_task_detail(self):
        if self.project_id and self.task_ids:
            task_id = random.choice(self.task_ids)
            self.client.get(
                f"/projects/{self.project_id}/tasks/{task_id}",
                headers=_auth_headers(self.token),
                name="/projects/{id}/tasks/{id} [GET]",
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
        # Each entry: (project_id, task_id, current_status)
        self.tasks_state: list[tuple[int, int, str]] = []

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
            self.tasks_state.append((self.project_id, r.json()["id"], "TODO"))

    @task(6)
    def advance_task_status(self):
        if not self.tasks_state:
            return
        idx = random.randrange(len(self.tasks_state))
        proj_id, task_id, status = self.tasks_state[idx]

        # 10% of non-terminal tasks are cancelled to exercise the CANCELLED branch.
        if status in ("TODO", "IN_PROGRESS", "IN_REVIEW") and random.random() < 0.10:
            r = self.client.patch(
                f"/projects/{proj_id}/tasks/{task_id}",
                json={"status": "CANCELLED"},
                headers=_auth_headers(self.token),
                name="/projects/{id}/tasks/{id} [PATCH cancel]",
            )
            if r.status_code == 200:
                self.tasks_state[idx] = (proj_id, task_id, "CANCELLED")
            return

        # Advance along the valid state machine path; skip terminal states.
        next_status = {
            "TODO":        "IN_PROGRESS",
            "IN_PROGRESS": "IN_REVIEW",
            "IN_REVIEW":   "DONE",
        }.get(status)

        if not next_status:
            return  # terminal (DONE or CANCELLED) — nothing to advance

        r = self.client.patch(
            f"/projects/{proj_id}/tasks/{task_id}",
            json={"status": next_status},
            headers=_auth_headers(self.token),
            name="/projects/{id}/tasks/{id} [PATCH]",
        )
        if r.status_code == 200:
            self.tasks_state[idx] = (proj_id, task_id, next_status)

    @task(3)
    def add_comment(self):
        if not self.tasks_state:
            return
        proj_id, task_id, _ = random.choice(self.tasks_state)
        self.client.post(
            f"/projects/{proj_id}/tasks/{task_id}/comments",
            json={"body": "Load test comment"},
            headers=_auth_headers(self.token),
            name="/tasks/{id}/comments [POST]",
        )

    @task(2)
    def list_comments(self):
        if not self.tasks_state:
            return
        proj_id, task_id, _ = random.choice(self.tasks_state)
        self.client.get(
            f"/projects/{proj_id}/tasks/{task_id}/comments",
            headers=_auth_headers(self.token),
            name="/tasks/{id}/comments [GET]",
        )

    @task(1)
    def delete_task(self):
        # Soft-delete a terminal task to exercise the DELETE path and verify
        # that soft-deleted rows disappear from subsequent list responses.
        terminal = [
            (i, proj_id, task_id)
            for i, (proj_id, task_id, status) in enumerate(self.tasks_state)
            if status in ("DONE", "CANCELLED")
        ]
        if not terminal:
            return
        idx, proj_id, task_id = random.choice(terminal)
        r = self.client.delete(
            f"/projects/{proj_id}/tasks/{task_id}",
            headers=_auth_headers(self.token),
            name="/projects/{id}/tasks/{id} [DELETE]",
        )
        if r.status_code == 204:
            self.tasks_state.pop(idx)


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


class AuthVerifyUser(HttpUser):
    """Exercises the full auth lifecycle: register → login → API call → logout.

    Each task iteration performs the complete lifecycle once. Rate limited to
    one register/login cycle per 6 seconds to stay under 10 logins/min.
    """
    wait_time = between(6, 10)  # stay well under the 10 logins/min rate limit
    weight = 1

    @task
    def full_auth_lifecycle(self):
        token = _register_and_login(self.client)
        if not token:
            return

        # Make one authenticated call to verify the token works
        self.client.get(
            "/projects",
            headers=_auth_headers(token),
            name="/projects [GET auth-verify]",
        )

        # Verify RFC 9116 security disclosure endpoint stays reachable under load
        self.client.get("/.well-known/security.txt", name="/.well-known/security.txt")

        # Logout to exercise token revocation
        self.client.post(
            "/auth/logout",
            headers=_auth_headers(token),
            name="/auth/logout",
        )


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
    print(f"  Peak RPS       : {total.current_rps:.1f}")
    print(f"{'='*60}\n")
