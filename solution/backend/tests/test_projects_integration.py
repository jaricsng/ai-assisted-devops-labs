"""Integration tests for project endpoints — covers CRUD and IDOR protection."""
import pytest
from httpx import AsyncClient


async def register_and_login(client: AsyncClient, email: str, password: str = "Test123!") -> str:
    await client.post("/auth/register", json={
        "email": email, "full_name": "Test User", "password": password
    })
    resp = await client.post("/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


@pytest.fixture
async def alice_token(client: AsyncClient) -> str:
    return await register_and_login(client, "alice_proj@example.com")


@pytest.fixture
async def bob_token(client: AsyncClient) -> str:
    return await register_and_login(client, "bob_proj@example.com")


@pytest.fixture
async def alice_project(client: AsyncClient, alice_token: str) -> dict:
    resp = await client.post(
        "/projects",
        json={"name": "Alice's Project", "description": "Private"},
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    return resp.json()


class TestCreateProject:
    async def test_create_project_returns_201(self, client: AsyncClient, alice_token: str):
        resp = await client.post(
            "/projects",
            json={"name": "My Project"},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "My Project"

    async def test_create_project_unauthenticated_returns_403(self, client: AsyncClient):
        resp = await client.post("/projects", json={"name": "Fail"})
        assert resp.status_code in (401, 403)


class TestListProjects:
    async def test_list_returns_only_own_projects(
        self, client: AsyncClient, alice_token: str, bob_token: str
    ):
        await client.post("/projects", json={"name": "Alice"}, headers={"Authorization": f"Bearer {alice_token}"})
        await client.post("/projects", json={"name": "Bob"}, headers={"Authorization": f"Bearer {bob_token}"})

        alice_resp = await client.get("/projects", headers={"Authorization": f"Bearer {alice_token}"})
        assert all(p["name"] == "Alice" for p in alice_resp.json())

    async def test_empty_list_for_new_user(self, client: AsyncClient):
        token = await register_and_login(client, "newuser_proj@example.com")
        resp = await client.get("/projects", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetProject:
    async def test_get_own_project_returns_200(
        self, client: AsyncClient, alice_token: str, alice_project: dict
    ):
        resp = await client.get(
            f"/projects/{alice_project['id']}",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == alice_project["id"]

    async def test_idor_other_user_project_returns_404(
        self, client: AsyncClient, bob_token: str, alice_project: dict
    ):
        """Bob must not be able to read Alice's project — 403 or 404, not 200."""
        resp = await client.get(
            f"/projects/{alice_project['id']}",
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        assert resp.status_code in (403, 404)

    async def test_nonexistent_project_returns_404(self, client: AsyncClient, alice_token: str):
        resp = await client.get("/projects/99999", headers={"Authorization": f"Bearer {alice_token}"})
        assert resp.status_code == 404


class TestDeleteProject:
    async def test_delete_own_project_returns_204(
        self, client: AsyncClient, alice_token: str, alice_project: dict
    ):
        resp = await client.delete(
            f"/projects/{alice_project['id']}",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert resp.status_code == 204

    async def test_idor_delete_other_user_project_returns_404(
        self, client: AsyncClient, bob_token: str, alice_project: dict
    ):
        resp = await client.delete(
            f"/projects/{alice_project['id']}",
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        assert resp.status_code in (403, 404)
