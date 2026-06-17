"""Integration tests for the projects router and project_repository."""

import uuid

from httpx import AsyncClient


async def _register_and_login(client: AsyncClient) -> str:
    email = f"proj_{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/auth/register",
        json={"email": email, "full_name": "Test User", "password": "Test1234!"},
    )
    resp = await client.post(
        "/auth/login",
        json={"email": email, "password": "Test1234!"},
    )
    return resp.json()["access_token"]


async def test_create_project(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post("/projects", json={"name": "Alpha"}, headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Alpha"
    assert body["id"] is not None


async def test_list_projects_includes_created(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    await client.post("/projects", json={"name": "Listed"}, headers=headers)
    resp = await client.get("/projects", headers=headers)

    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "Listed" in names


async def test_get_project_by_id(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    project_id = (
        await client.post("/projects", json={"name": "Fetchable"}, headers=headers)
    ).json()["id"]

    resp = await client.get(f"/projects/{project_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == project_id


async def test_get_nonexistent_project_returns_404(client: AsyncClient):
    token = await _register_and_login(client)
    resp = await client.get(
        "/projects/999999", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404


async def test_delete_project_returns_204(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    project_id = (
        await client.post("/projects", json={"name": "Deletable"}, headers=headers)
    ).json()["id"]

    resp = await client.delete(f"/projects/{project_id}", headers=headers)
    assert resp.status_code == 204


async def test_deleted_project_not_returned(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    project_id = (
        await client.post("/projects", json={"name": "Gone"}, headers=headers)
    ).json()["id"]
    await client.delete(f"/projects/{project_id}", headers=headers)

    resp = await client.get(f"/projects/{project_id}", headers=headers)
    assert resp.status_code == 404


async def test_delete_nonexistent_project_returns_404(client: AsyncClient):
    token = await _register_and_login(client)
    resp = await client.delete(
        "/projects/999999", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404


async def test_idor_user_b_cannot_read_user_a_project(client: AsyncClient):
    token_a = await _register_and_login(client)
    token_b = await _register_and_login(client)

    project_id = (
        await client.post(
            "/projects",
            json={"name": "Secret"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
    ).json()["id"]

    resp = await client.get(
        f"/projects/{project_id}", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 404


async def test_idor_user_b_cannot_delete_user_a_project(client: AsyncClient):
    token_a = await _register_and_login(client)
    token_b = await _register_and_login(client)

    project_id = (
        await client.post(
            "/projects",
            json={"name": "Protected"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
    ).json()["id"]

    resp = await client.delete(
        f"/projects/{project_id}", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 404
