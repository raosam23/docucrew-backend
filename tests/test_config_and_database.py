"""Settings defaults and the database helpers, without opening a connection."""

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.db.database import get_session, init_db
from sqlmodel import SQLModel


def test_imported_settings_follow_the_process_environment() -> None:
    """Settings are built from the environment bootstrap (or CI) installed before import."""
    assert settings.APP_ENV == os.environ["APP_ENV"] == "test"
    assert settings.DEBUG is False
    assert settings.OPENAI_API_KEY == os.environ["OPENAI_API_KEY"]
    assert settings.TAVILY_API_KEY == os.environ["TAVILY_API_KEY"]
    assert settings.SECRET_KEY == os.environ["SECRET_KEY"]
    assert settings.DATABASE_URL == os.environ["DATABASE_URL"]
    assert settings.SALT_ROUNDS == int(os.environ["SALT_ROUNDS"])
    assert settings.OPENAI_API_KEY.startswith("sk-")
    assert settings.TAVILY_API_KEY.startswith("tvly-")


def test_settings_defaults_when_optional_env_is_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "APP_NAME",
        "ALGORITHM",
        "ACCESS_TOKEN_EXPIRE_MINUTES",
        "SALT_ROUNDS",
        "OPENAI_MODEL",
        "EMBEDDING_MODEL",
        "CHROMA_PERSIST_DIR",
        "REDIS_URL",
        "ALLOWED_ORIGINS",
    ):
        monkeypatch.delenv(key, raising=False)

    configured = Settings(
        APP_ENV="test",
        DEBUG=False,
        DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/test",
        SECRET_KEY="secret",
        OPENAI_API_KEY="sk-test",
        TAVILY_API_KEY="tvly-test",
        _env_file=None,
    )

    assert configured.APP_NAME == "DocuCrew"
    assert configured.ALGORITHM == "HS256"
    assert configured.ACCESS_TOKEN_EXPIRE_MINUTES == 60
    assert configured.SALT_ROUNDS == 12
    assert configured.OPENAI_MODEL == "gpt-4o-mini"
    assert configured.EMBEDDING_MODEL == "text-embedding-3-small"
    assert configured.CHROMA_PERSIST_DIR == "./chroma_data"
    assert configured.REDIS_URL == "redis://localhost:6379"
    assert configured.ALLOWED_ORIGINS == ["http://localhost:3000"]


def test_settings_require_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "APP_ENV",
        "DEBUG",
        "DATABASE_URL",
        "SECRET_KEY",
        "OPENAI_API_KEY",
        "TAVILY_API_KEY",
        "APP_NAME",
        "ALGORITHM",
        "SALT_ROUNDS",
        "OPENAI_MODEL",
        "EMBEDDING_MODEL",
        "CHROMA_PERSIST_DIR",
        "REDIS_URL",
        "ALLOWED_ORIGINS",
        "ACCESS_TOKEN_EXPIRE_MINUTES",
    ):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.asyncio
async def test_get_session_yields_the_async_session(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    context = AsyncMock()
    context.__aenter__.return_value = session
    context.__aexit__.return_value = False

    def _factory(*_args: object, **kwargs: object) -> AsyncMock:
        assert kwargs["expire_on_commit"] is False
        return context

    monkeypatch.setattr("app.db.database.AsyncSession", _factory)

    generator = get_session()
    assert await anext(generator) is session
    with pytest.raises(StopAsyncIteration):
        await anext(generator)
    context.__aexit__.assert_awaited()


@pytest.mark.asyncio
async def test_init_db_creates_tables_on_the_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = AsyncMock()
    context = AsyncMock()
    context.__aenter__.return_value = connection
    context.__aexit__.return_value = False
    engine = MagicMock()
    engine.begin.return_value = context
    monkeypatch.setattr("app.db.database.engine", engine)

    await init_db()

    connection.run_sync.assert_awaited_once()
    assert connection.run_sync.await_args is not None
    assert connection.run_sync.await_args.args[0] == SQLModel.metadata.create_all
