"""Collection routes. Chroma deletion is mocked; the session never touches Postgres."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from tests.factories import COLLECTION_ID, make_collection, rows_result, scalar_result


def test_create_collection_assigns_a_chroma_id(auth_client: TestClient, mock_session: AsyncMock) -> None:
    response = auth_client.post(
        "/api/collections/",
        json={"name": "Research", "description": "Papers"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Research"
    assert body["description"] == "Papers"
    assert body["user_id"] == "11111111-1111-1111-1111-111111111111"
    assert body["chroma_collection_id"] == f"col_{body['id']}"
    assert body["created_at"]
    mock_session.add.assert_called_once()
    mock_session.commit.assert_awaited()


def test_create_collection_allows_a_missing_description(auth_client: TestClient) -> None:
    response = auth_client.post("/api/collections/", json={"name": "Scratch"})

    assert response.status_code == 201
    assert response.json()["description"] is None


def test_create_collection_requires_a_name(auth_client: TestClient) -> None:
    assert auth_client.post("/api/collections/", json={}).status_code == 422


def test_list_collections_returns_the_users_rows(auth_client: TestClient, mock_session: AsyncMock) -> None:
    first = make_collection()
    second = make_collection(name="Archive", description=None)
    mock_session.execute = AsyncMock(return_value=rows_result([first, second]))

    response = auth_client.get("/api/collections/")

    assert response.status_code == 200
    body = response.json()
    assert [item["name"] for item in body] == ["Policies", "Archive"]
    assert body[1]["description"] is None


def test_list_collections_can_be_empty(auth_client: TestClient, mock_session: AsyncMock) -> None:
    mock_session.execute = AsyncMock(return_value=rows_result([]))

    assert auth_client.get("/api/collections/").json() == []


def test_get_collection_by_id(auth_client: TestClient, mock_session: AsyncMock) -> None:
    mock_session.execute = AsyncMock(return_value=scalar_result(make_collection()))

    response = auth_client.get(f"/api/collections/{COLLECTION_ID}")

    assert response.status_code == 200
    assert response.json()["id"] == str(COLLECTION_ID)


def test_get_collection_returns_404_when_missing(auth_client: TestClient, mock_session: AsyncMock) -> None:
    mock_session.execute = AsyncMock(return_value=scalar_result(None))

    response = auth_client.get(f"/api/collections/{COLLECTION_ID}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Collection not found"


def test_delete_collection_removes_the_chroma_collection(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collection = make_collection()
    mock_session.execute = AsyncMock(return_value=scalar_result(collection))
    deleted = MagicMock()
    monkeypatch.setattr("app.api.routes.collections.delete_collection", deleted)

    response = auth_client.delete(f"/api/collections/{COLLECTION_ID}")

    assert response.status_code == 204
    assert response.content == b""
    deleted.assert_called_once_with(collection.chroma_collection_id)
    mock_session.delete.assert_awaited_once()
    mock_session.commit.assert_awaited()


def test_delete_collection_returns_404_without_touching_chroma(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_session.execute = AsyncMock(return_value=scalar_result(None))
    deleted = MagicMock()
    monkeypatch.setattr("app.api.routes.collections.delete_collection", deleted)

    response = auth_client.delete(f"/api/collections/{COLLECTION_ID}")

    assert response.status_code == 404
    deleted.assert_not_called()
    mock_session.delete.assert_not_called()
