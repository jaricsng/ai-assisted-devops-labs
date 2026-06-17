"""Integration tests for tasks and comments routers, task_repository, comment_repository."""

import uuid

from httpx import AsyncClient


async def _setup(client: AsyncClient) -> tuple[dict, int]:
    """Register a user, login, create a project. Returns (auth headers, project_id)."""
    email = f"task_{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/auth/register",
        json={"email": email, "full_name": "Task User", "password": "Test1234!"},
    )
    token = (
        await client.post("/auth/login", json={"email": email, "password": "Test1234!"})
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = (
        await client.post("/projects", json={"name": "Task Project"}, headers=headers)
    ).json()["id"]
    return headers, project_id


async def test_create_task(client: AsyncClient):
    headers, pid = await _setup(client)
    resp = await client.post(
        f"/projects/{pid}/tasks",
        json={"title": "First Task", "priority": "HIGH"},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "First Task"
    assert body["status"] == "TODO"
    assert body["priority"] == "HIGH"


async def test_list_tasks(client: AsyncClient):
    headers, pid = await _setup(client)
    await client.post(
        f"/projects/{pid}/tasks",
        json={"title": "T1", "priority": "LOW"},
        headers=headers,
    )
    await client.post(
        f"/projects/{pid}/tasks",
        json={"title": "T2", "priority": "LOW"},
        headers=headers,
    )

    resp = await client.get(f"/projects/{pid}/tasks", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_get_task(client: AsyncClient):
    headers, pid = await _setup(client)
    task_id = (
        await client.post(
            f"/projects/{pid}/tasks",
            json={"title": "Fetch Me", "priority": "LOW"},
            headers=headers,
        )
    ).json()["id"]

    resp = await client.get(f"/projects/{pid}/tasks/{task_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == task_id


async def test_get_nonexistent_task_returns_404(client: AsyncClient):
    headers, pid = await _setup(client)
    resp = await client.get(f"/projects/{pid}/tasks/999999", headers=headers)
    assert resp.status_code == 404


async def test_update_task_title(client: AsyncClient):
    headers, pid = await _setup(client)
    task_id = (
        await client.post(
            f"/projects/{pid}/tasks",
            json={"title": "Old", "priority": "LOW"},
            headers=headers,
        )
    ).json()["id"]

    resp = await client.patch(
        f"/projects/{pid}/tasks/{task_id}", json={"title": "New"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "New"


async def test_status_transition_todo_to_in_progress(client: AsyncClient):
    headers, pid = await _setup(client)
    task_id = (
        await client.post(
            f"/projects/{pid}/tasks",
            json={"title": "Move Me", "priority": "MEDIUM"},
            headers=headers,
        )
    ).json()["id"]

    resp = await client.patch(
        f"/projects/{pid}/tasks/{task_id}",
        json={"status": "IN_PROGRESS"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "IN_PROGRESS"


async def test_status_transition_full_happy_path(client: AsyncClient):
    headers, pid = await _setup(client)
    task_id = (
        await client.post(
            f"/projects/{pid}/tasks",
            json={"title": "Full Path", "priority": "MEDIUM"},
            headers=headers,
        )
    ).json()["id"]

    for next_status in ("IN_PROGRESS", "IN_REVIEW", "DONE"):
        resp = await client.patch(
            f"/projects/{pid}/tasks/{task_id}",
            json={"status": next_status},
            headers=headers,
        )
        assert resp.status_code == 200, f"Transition to {next_status} failed"
        assert resp.json()["status"] == next_status


async def test_invalid_status_transition_returns_422(client: AsyncClient):
    headers, pid = await _setup(client)
    task_id = (
        await client.post(
            f"/projects/{pid}/tasks",
            json={"title": "Bad Jump", "priority": "LOW"},
            headers=headers,
        )
    ).json()["id"]

    resp = await client.patch(
        f"/projects/{pid}/tasks/{task_id}", json={"status": "DONE"}, headers=headers
    )
    assert resp.status_code == 422


async def test_terminal_state_cannot_transition(client: AsyncClient):
    headers, pid = await _setup(client)
    task_id = (
        await client.post(
            f"/projects/{pid}/tasks",
            json={"title": "Terminal", "priority": "LOW"},
            headers=headers,
        )
    ).json()["id"]

    await client.patch(
        f"/projects/{pid}/tasks/{task_id}",
        json={"status": "CANCELLED"},
        headers=headers,
    )
    resp = await client.patch(
        f"/projects/{pid}/tasks/{task_id}", json={"status": "TODO"}, headers=headers
    )
    assert resp.status_code == 422


async def test_delete_task_soft_deletes(client: AsyncClient):
    headers, pid = await _setup(client)
    task_id = (
        await client.post(
            f"/projects/{pid}/tasks",
            json={"title": "Doomed", "priority": "LOW"},
            headers=headers,
        )
    ).json()["id"]

    assert (
        await client.delete(f"/projects/{pid}/tasks/{task_id}", headers=headers)
    ).status_code == 204
    assert (
        await client.get(f"/projects/{pid}/tasks/{task_id}", headers=headers)
    ).status_code == 404


async def test_create_and_list_comment(client: AsyncClient):
    headers, pid = await _setup(client)
    task_id = (
        await client.post(
            f"/projects/{pid}/tasks",
            json={"title": "Discuss", "priority": "LOW"},
            headers=headers,
        )
    ).json()["id"]

    resp = await client.post(
        f"/projects/{pid}/tasks/{task_id}/comments",
        json={"body": "Looks good!"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["body"] == "Looks good!"

    list_resp = await client.get(
        f"/projects/{pid}/tasks/{task_id}/comments", headers=headers
    )
    assert list_resp.status_code == 200
    assert any(c["body"] == "Looks good!" for c in list_resp.json())


async def test_tasks_in_wrong_project_return_404(client: AsyncClient):
    headers, pid = await _setup(client)
    _, other_pid = await _setup(client)

    task_id = (
        await client.post(
            f"/projects/{pid}/tasks",
            json={"title": "Wrong Project", "priority": "LOW"},
            headers=headers,
        )
    ).json()["id"]

    resp = await client.get(f"/projects/{other_pid}/tasks/{task_id}", headers=headers)
    assert resp.status_code == 404


# ── IDOR: Task-level access control ──────────────────────────────────────────


async def _create_task(
    client: AsyncClient, headers: dict, pid: int, title: str = "Private Task"
) -> int:
    return (
        await client.post(
            f"/projects/{pid}/tasks",
            json={"title": title, "priority": "LOW"},
            headers=headers,
        )
    ).json()["id"]


async def test_idor_user_b_cannot_read_user_a_task(client: AsyncClient):
    """GET /projects/:pid/tasks/:tid must return 404 when the project belongs to another user."""
    headers_a, pid_a = await _setup(client)
    headers_b, _ = await _setup(client)
    task_id = await _create_task(client, headers_a, pid_a)

    resp = await client.get(f"/projects/{pid_a}/tasks/{task_id}", headers=headers_b)
    assert resp.status_code == 404


async def test_idor_user_b_cannot_update_user_a_task(client: AsyncClient):
    """PATCH /projects/:pid/tasks/:tid must return 404 when the project belongs to another user."""
    headers_a, pid_a = await _setup(client)
    headers_b, _ = await _setup(client)
    task_id = await _create_task(client, headers_a, pid_a)

    resp = await client.patch(
        f"/projects/{pid_a}/tasks/{task_id}",
        json={"title": "Hijacked"},
        headers=headers_b,
    )
    assert resp.status_code == 404


async def test_idor_user_b_cannot_delete_user_a_task(client: AsyncClient):
    """DELETE /projects/:pid/tasks/:tid must return 404 when the project belongs to another user."""
    headers_a, pid_a = await _setup(client)
    headers_b, _ = await _setup(client)
    task_id = await _create_task(client, headers_a, pid_a)

    resp = await client.delete(f"/projects/{pid_a}/tasks/{task_id}", headers=headers_b)
    assert resp.status_code == 404


async def test_idor_user_b_cannot_comment_on_user_a_task(client: AsyncClient):
    """POST /projects/:pid/tasks/:tid/comments must return 404 when project belongs to another user."""
    headers_a, pid_a = await _setup(client)
    headers_b, _ = await _setup(client)
    task_id = await _create_task(client, headers_a, pid_a)

    resp = await client.post(
        f"/projects/{pid_a}/tasks/{task_id}/comments",
        json={"body": "Injected comment"},
        headers=headers_b,
    )
    assert resp.status_code == 404


# ── Status transitions ────────────────────────────────────────────────────────


async def test_cancel_transition_via_api(client: AsyncClient):
    """PATCH status=CANCELLED from TODO must succeed and set terminal state."""
    headers, pid = await _setup(client)
    task_id = await _create_task(client, headers, pid, title="To Cancel")

    resp = await client.patch(
        f"/projects/{pid}/tasks/{task_id}",
        json={"status": "CANCELLED"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"


# ── Field updates ─────────────────────────────────────────────────────────────


async def test_update_task_priority_and_description(client: AsyncClient):
    """PATCH with priority and description must update both fields independently of status."""
    headers, pid = await _setup(client)
    task_id = (
        await client.post(
            f"/projects/{pid}/tasks",
            json={"title": "Field Update", "priority": "HIGH"},
            headers=headers,
        )
    ).json()["id"]

    resp = await client.patch(
        f"/projects/{pid}/tasks/{task_id}",
        json={"priority": "LOW", "description": "Updated description"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["priority"] == "LOW"
    assert body["description"] == "Updated description"
    assert body["status"] == "TODO"  # status unchanged


# ── Task filtering (Module 05 feature) ───────────────────────────────────────


async def test_filter_tasks_by_status(client: AsyncClient):
    """GET /projects/{id}/tasks?status=TODO returns only TODO tasks."""
    headers, pid = await _setup(client)
    await client.post(
        f"/projects/{pid}/tasks",
        json={"title": "Todo Task", "priority": "LOW"},
        headers=headers,
    )
    task_id = (
        await client.post(
            f"/projects/{pid}/tasks",
            json={"title": "Progress Task", "priority": "LOW"},
            headers=headers,
        )
    ).json()["id"]
    await client.patch(
        f"/projects/{pid}/tasks/{task_id}",
        json={"status": "IN_PROGRESS"},
        headers=headers,
    )

    resp = await client.get(f"/projects/{pid}/tasks?status=TODO", headers=headers)
    assert resp.status_code == 200
    tasks = resp.json()
    assert all(t["status"] == "TODO" for t in tasks)
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Todo Task"


async def test_filter_tasks_by_priority(client: AsyncClient):
    """GET /projects/{id}/tasks?priority=HIGH returns only HIGH priority tasks."""
    headers, pid = await _setup(client)
    await client.post(
        f"/projects/{pid}/tasks",
        json={"title": "High Task", "priority": "HIGH"},
        headers=headers,
    )
    await client.post(
        f"/projects/{pid}/tasks",
        json={"title": "Low Task", "priority": "LOW"},
        headers=headers,
    )

    resp = await client.get(f"/projects/{pid}/tasks?priority=HIGH", headers=headers)
    assert resp.status_code == 200
    tasks = resp.json()
    assert all(t["priority"] == "HIGH" for t in tasks)
    assert len(tasks) == 1


async def test_filter_tasks_by_status_and_priority(client: AsyncClient):
    """GET /projects/{id}/tasks?status=TODO&priority=HIGH returns combined filter."""
    headers, pid = await _setup(client)
    await client.post(
        f"/projects/{pid}/tasks",
        json={"title": "High Todo", "priority": "HIGH"},
        headers=headers,
    )
    await client.post(
        f"/projects/{pid}/tasks",
        json={"title": "Low Todo", "priority": "LOW"},
        headers=headers,
    )
    await client.post(
        f"/projects/{pid}/tasks",
        json={"title": "High Progress", "priority": "HIGH"},
        headers=headers,
    )

    resp = await client.get(
        f"/projects/{pid}/tasks?status=TODO&priority=HIGH", headers=headers
    )
    assert resp.status_code == 200
    tasks = resp.json()
    assert len(tasks) == 2
    assert all(t["status"] == "TODO" and t["priority"] == "HIGH" for t in tasks)


async def test_filter_tasks_no_match_returns_empty_list(client: AsyncClient):
    """Filter returning no results should return [] not 404."""
    headers, pid = await _setup(client)
    await client.post(
        f"/projects/{pid}/tasks",
        json={"title": "Only Task", "priority": "LOW"},
        headers=headers,
    )

    resp = await client.get(f"/projects/{pid}/tasks?status=DONE", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


# ── Comment audit log ────────────────────────────────────────────────────────


async def test_create_comment_emits_audit_log(client: AsyncClient):
    """POST /comments must emit a COMMENT_CREATED audit event with resource_id and task_id."""
    from structlog.testing import capture_logs

    headers, pid = await _setup(client)
    task_id = await _create_task(client, headers, pid)

    with capture_logs() as cap:
        resp = await client.post(
            f"/projects/{pid}/tasks/{task_id}/comments",
            json={"body": "Audit me"},
            headers=headers,
        )
    assert resp.status_code == 201
    audit = [
        e
        for e in cap
        if e.get("event") == "audit" and e.get("action") == "COMMENT_CREATED"
    ]
    assert len(audit) == 1
    assert audit[0]["resource"] == "comment"
    assert "resource_id" in audit[0]
    assert audit[0]["task_id"] == task_id
