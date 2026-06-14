"""Integration tests for task endpoints — status transitions and access control."""
import pytest
from httpx import AsyncClient


async def register_and_login(client: AsyncClient, email: str) -> str:
    await client.post("/auth/register", json={
        "email": email, "full_name": "User", "password": "Test123!"
    })
    resp = await client.post("/auth/login", json={"email": email, "password": "Test123!"})
    return resp.json()["access_token"]


@pytest.fixture
async def alice_token(client: AsyncClient) -> str:
    return await register_and_login(client, "alice_task@example.com")


@pytest.fixture
async def bob_token(client: AsyncClient) -> str:
    return await register_and_login(client, "bob_task@example.com")


@pytest.fixture
async def project(client: AsyncClient, alice_token: str) -> dict:
    resp = await client.post(
        "/projects",
        json={"name": "Test Project"},
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    return resp.json()


@pytest.fixture
async def task(client: AsyncClient, alice_token: str, project: dict) -> dict:
    resp = await client.post(
        f"/projects/{project['id']}/tasks",
        json={"title": "Test Task", "priority": "HIGH"},
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    return resp.json()


class TestCreateTask:
    async def test_create_task_returns_201_with_todo_status(
        self, client: AsyncClient, alice_token: str, project: dict
    ):
        resp = await client.post(
            f"/projects/{project['id']}/tasks",
            json={"title": "New Task", "priority": "MEDIUM"},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "TODO"
        assert data["title"] == "New Task"

    async def test_create_task_in_other_users_project_returns_404(
        self, client: AsyncClient, bob_token: str, project: dict
    ):
        resp = await client.post(
            f"/projects/{project['id']}/tasks",
            json={"title": "Intruder", "priority": "LOW"},
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        assert resp.status_code == 404


class TestStatusTransitions:
    async def test_todo_to_in_progress_allowed(
        self, client: AsyncClient, alice_token: str, project: dict, task: dict
    ):
        resp = await client.patch(
            f"/projects/{project['id']}/tasks/{task['id']}",
            json={"status": "IN_PROGRESS"},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "IN_PROGRESS"

    async def test_todo_to_done_returns_422(
        self, client: AsyncClient, alice_token: str, project: dict, task: dict
    ):
        resp = await client.patch(
            f"/projects/{project['id']}/tasks/{task['id']}",
            json={"status": "DONE"},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert resp.status_code == 422

    async def test_full_valid_path_todo_to_done(
        self, client: AsyncClient, alice_token: str, project: dict, task: dict
    ):
        headers = {"Authorization": f"Bearer {alice_token}"}
        base = f"/projects/{project['id']}/tasks/{task['id']}"
        for status in ("IN_PROGRESS", "IN_REVIEW", "DONE"):
            resp = await client.patch(base, json={"status": status}, headers=headers)
            assert resp.status_code == 200, f"Failed at transition to {status}"

    async def test_done_is_terminal(
        self, client: AsyncClient, alice_token: str, project: dict, task: dict
    ):
        headers = {"Authorization": f"Bearer {alice_token}"}
        base = f"/projects/{project['id']}/tasks/{task['id']}"
        for status in ("IN_PROGRESS", "IN_REVIEW", "DONE"):
            await client.patch(base, json={"status": status}, headers=headers)
        resp = await client.patch(base, json={"status": "TODO"}, headers=headers)
        assert resp.status_code == 422

    async def test_cancelled_is_terminal(
        self, client: AsyncClient, alice_token: str, project: dict, task: dict
    ):
        headers = {"Authorization": f"Bearer {alice_token}"}
        base = f"/projects/{project['id']}/tasks/{task['id']}"
        await client.patch(base, json={"status": "CANCELLED"}, headers=headers)
        resp = await client.patch(base, json={"status": "TODO"}, headers=headers)
        assert resp.status_code == 422


class TestTaskIDOR:
    async def test_bob_cannot_update_alices_task(
        self, client: AsyncClient, bob_token: str, project: dict, task: dict
    ):
        resp = await client.patch(
            f"/projects/{project['id']}/tasks/{task['id']}",
            json={"status": "IN_PROGRESS"},
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        assert resp.status_code in (403, 404)

    async def test_bob_cannot_delete_alices_task(
        self, client: AsyncClient, bob_token: str, project: dict, task: dict
    ):
        resp = await client.delete(
            f"/projects/{project['id']}/tasks/{task['id']}",
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        assert resp.status_code in (403, 404)


class TestComments:
    async def test_add_comment_returns_201(
        self, client: AsyncClient, alice_token: str, project: dict, task: dict
    ):
        resp = await client.post(
            f"/projects/{project['id']}/tasks/{task['id']}/comments",
            json={"body": "Looking good!"},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["body"] == "Looking good!"

    async def test_list_comments_returns_in_order(
        self, client: AsyncClient, alice_token: str, project: dict, task: dict
    ):
        headers = {"Authorization": f"Bearer {alice_token}"}
        base = f"/projects/{project['id']}/tasks/{task['id']}/comments"
        await client.post(base, json={"body": "First"}, headers=headers)
        await client.post(base, json={"body": "Second"}, headers=headers)
        resp = await client.get(base, headers=headers)
        bodies = [c["body"] for c in resp.json()]
        assert bodies == ["First", "Second"]
