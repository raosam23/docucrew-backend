"""Shared fixtures.

External systems are replaced here: the async database session, the authenticated
user, and FastAPI dependency overrides. LLM calls, Chroma, and Tavily are patched
in the tests that would otherwise reach them. No test needs a network connection
or a real API key.
"""

from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.bootstrap import ENV_READY
from tests.factories import NOW, make_user

from app.core.security import get_current_user
from app.db.database import get_session
from app.main import app
from app.models.user import User


def pytest_configure(config: pytest.Config) -> None:
    if not ENV_READY:
        raise RuntimeError("test environment was not initialised")


@pytest.fixture
def mock_user() -> User:
    """Authenticated user returned by the auth dependency override."""
    return make_user()


@pytest.fixture
def mock_session() -> AsyncMock:
    """AsyncSession double. add() stays synchronous, matching SQLAlchemy."""
    session = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    result.scalars.return_value.first.return_value = None
    result.scalar_one_or_none.return_value = None

    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.delete = AsyncMock()
    session.get = AsyncMock(return_value=None)
    session.rollback = AsyncMock()
    session.flush = AsyncMock()

    async def _refresh(obj: object) -> None:
        if getattr(obj, "created_at", None) is None:
            obj.created_at = NOW  # type: ignore[attr-defined]

    session.refresh = AsyncMock(side_effect=_refresh)
    return session


@pytest.fixture
def client(mock_session: AsyncMock) -> Iterator[TestClient]:
    """TestClient whose database dependency is the mock session."""

    async def _get_session() -> AsyncIterator[AsyncMock]:
        yield mock_session

    app.dependency_overrides[get_session] = _get_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def auth_client(client: TestClient, mock_user: User) -> TestClient:
    """TestClient that is already authenticated as mock_user."""

    async def _current_user() -> User:
        return mock_user

    app.dependency_overrides[get_current_user] = _current_user
    return client


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run the test with cwd in a temp directory so ./uploads stays isolated."""
    monkeypatch.chdir(tmp_path)
    return tmp_path
