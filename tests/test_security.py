"""Password hashing and the cookie JWT dependency."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from jose import jwt

from app.core.config import settings
from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from tests.factories import make_user, scalar_result


def test_hash_password_verifies_and_uses_a_salt() -> None:
    hashed = hash_password("correct horse")
    other = hash_password("correct horse")

    assert hashed != "correct horse"
    assert hashed.startswith("$2")
    assert hashed != other
    assert verify_password("correct horse", hashed) is True
    assert verify_password("wrong horse", hashed) is False


def test_create_access_token_signs_the_subject() -> None:
    token = create_access_token({"sub": "ada@example.com"})
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    assert payload["sub"] == "ada@example.com"
    assert "exp" in payload


def _request(token: str | None) -> MagicMock:
    request = MagicMock()
    request.cookies.get.return_value = token
    return request


@pytest.mark.asyncio
async def test_get_current_user_requires_a_cookie() -> None:
    with pytest.raises(HTTPException) as exc:
        await get_current_user(_request(None), AsyncMock())

    assert exc.value.status_code == 401
    assert exc.value.detail == "Not authenticated"


@pytest.mark.asyncio
async def test_get_current_user_rejects_a_bad_token() -> None:
    with pytest.raises(HTTPException) as exc:
        await get_current_user(_request("not-a-jwt"), AsyncMock())

    assert exc.value.status_code == 401
    assert "Invalid token" in exc.value.detail


@pytest.mark.asyncio
async def test_get_current_user_rejects_a_tampered_token() -> None:
    token = create_access_token({"sub": "ada@example.com"}) + "x"

    with pytest.raises(HTTPException) as exc:
        await get_current_user(_request(token), AsyncMock())

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_rejects_an_expired_token() -> None:
    token = jwt.encode(
        {"sub": "ada@example.com", "exp": datetime.now(timezone.utc) - timedelta(minutes=5)},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    with pytest.raises(HTTPException) as exc:
        await get_current_user(_request(token), AsyncMock())

    assert exc.value.status_code == 401
    assert "Invalid token" in exc.value.detail


@pytest.mark.asyncio
async def test_get_current_user_rejects_a_token_without_a_subject() -> None:
    token = jwt.encode(
        {"exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    with pytest.raises(HTTPException) as exc:
        await get_current_user(_request(token), AsyncMock())

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid token"


@pytest.mark.asyncio
async def test_get_current_user_rejects_an_unknown_email() -> None:
    token = create_access_token({"sub": "missing@example.com"})
    session = AsyncMock()
    session.execute = AsyncMock(return_value=scalar_result(None))

    with pytest.raises(HTTPException) as exc:
        await get_current_user(_request(token), session)

    assert exc.value.status_code == 401
    assert exc.value.detail == "User not found"


@pytest.mark.asyncio
async def test_get_current_user_returns_the_matching_user() -> None:
    user = make_user()
    token = create_access_token({"sub": user.email})
    session = AsyncMock()
    session.execute = AsyncMock(return_value=scalar_result(user))

    found = await get_current_user(_request(token), session)

    assert found is user
