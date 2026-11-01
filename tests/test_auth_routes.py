"""Auth routes through TestClient. The session is an AsyncMock; passwords are real bcrypt."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from tests.factories import (
    COLLECTION_ID,
    DOCUMENT_ID,
    make_user,
    scalar_result,
)


def test_register_creates_a_user(client: TestClient, mock_session: AsyncMock) -> None:
    mock_session.execute = AsyncMock(return_value=scalar_result(None))

    response = client.post(
        "/api/auth/register",
        json={"email": "grace@example.com", "password": "secret-pass", "name": "Grace"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "grace@example.com"
    assert body["name"] == "Grace"
    assert body["created_at"]
    assert "password" not in body
    assert "set-cookie" not in response.headers
    mock_session.add.assert_called_once()
    mock_session.commit.assert_awaited()


def test_register_allows_a_missing_name(client: TestClient, mock_session: AsyncMock) -> None:
    mock_session.execute = AsyncMock(return_value=scalar_result(None))

    response = client.post(
        "/api/auth/register",
        json={"email": "grace@example.com", "password": "secret-pass"},
    )

    assert response.status_code == 201
    assert response.json()["name"] is None


def test_register_rejects_a_duplicate_email(client: TestClient, mock_session: AsyncMock) -> None:
    mock_session.execute = AsyncMock(return_value=scalar_result(make_user()))

    response = client.post(
        "/api/auth/register",
        json={"email": "ada@example.com", "password": "secret-pass"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "User already exists"
    mock_session.add.assert_not_called()


def test_register_rejects_a_missing_password(client: TestClient) -> None:
    response = client.post("/api/auth/register", json={"email": "ada@example.com"})

    assert response.status_code == 422


def test_login_sets_an_httponly_cookie(client: TestClient, mock_session: AsyncMock) -> None:
    user = make_user(password_hash=hash_password("secret-pass"))
    mock_session.execute = AsyncMock(return_value=scalar_result(user))

    response = client.post(
        "/api/auth/login",
        json={"email": user.email, "password": "secret-pass"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == user.email
    assert "password" not in response.json()
    cookie = response.headers["set-cookie"]
    assert "access_token=" in cookie
    assert "httponly" in cookie.lower()
    assert "samesite=lax" in cookie.lower()


def test_login_cookie_authenticates_me(client: TestClient, mock_session: AsyncMock) -> None:
    user = make_user(password_hash=hash_password("secret-pass"))
    mock_session.execute = AsyncMock(side_effect=[scalar_result(user), scalar_result(user)])

    login = client.post("/api/auth/login", json={"email": user.email, "password": "secret-pass"})
    assert login.status_code == 200

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == str(user.id)


def test_login_rejects_unknown_and_wrong_passwords(client: TestClient, mock_session: AsyncMock) -> None:
    missing = client.post("/api/auth/login", json={"email": "nope@example.com", "password": "secret-pass"})
    assert missing.status_code == 401
    assert missing.json()["detail"] == "Invalid credentials"

    user = make_user(password_hash=hash_password("secret-pass"))
    mock_session.execute = AsyncMock(return_value=scalar_result(user))
    wrong = client.post("/api/auth/login", json={"email": user.email, "password": "nope"})
    assert wrong.status_code == 401
    assert wrong.json()["detail"] == "Invalid credentials"


def test_logout_clears_the_cookie(client: TestClient) -> None:
    response = client.post("/api/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"message": "Logged out successfully"}
    assert "access_token=" in response.headers["set-cookie"]


def test_me_requires_a_cookie(client: TestClient) -> None:
    assert client.get("/api/auth/me").status_code == 401


def test_me_rejects_a_bad_cookie(client: TestClient) -> None:
    client.cookies.set("access_token", "not-a-token")

    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_me_returns_the_override_user(auth_client: TestClient) -> None:
    response = auth_client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == "ada@example.com"


def test_me_rejects_a_token_for_an_unknown_user(client: TestClient, mock_session: AsyncMock) -> None:
    token = create_access_token({"sub": "ghost@example.com"})
    mock_session.execute = AsyncMock(return_value=scalar_result(None))
    client.cookies.set("access_token", token)

    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "User not found"


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("get", "/api/auth/me", {}),
        ("get", "/api/collections/", {}),
        ("post", "/api/collections/", {"json": {"name": "Notes"}}),
        ("get", f"/api/collections/{COLLECTION_ID}", {}),
        ("delete", f"/api/collections/{COLLECTION_ID}", {}),
        ("get", f"/api/collections/{COLLECTION_ID}/documents", {}),
        (
            "post",
            f"/api/collections/{COLLECTION_ID}/documents/",
            {"files": [("files", ("a.txt", b"hi", "text/plain"))]},
        ),
        ("delete", f"/api/collections/{COLLECTION_ID}/documents/{DOCUMENT_ID}", {}),
        ("post", f"/api/collections/{COLLECTION_ID}/query", {"json": {"question": "Why?"}}),
        ("post", f"/api/collections/{COLLECTION_ID}/query/stream", {"json": {"question": "Why?"}}),
        ("get", f"/api/collections/{COLLECTION_ID}/history", {}),
    ],
)
def test_protected_routes_reject_a_missing_cookie(
    client: TestClient,
    method: str,
    path: str,
    kwargs: dict,
) -> None:
    response = getattr(client, method)(path, **kwargs)

    assert response.status_code == 401
