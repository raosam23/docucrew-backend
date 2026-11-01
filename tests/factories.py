"""Builders for SQLModel rows and SQLAlchemy result doubles."""

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from app.models.collection import Collection
from app.models.document import Document, DocumentStatus, FileType
from app.models.query_history import QueryHistory
from app.models.user import User

NOW = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)

USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
COLLECTION_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
DOCUMENT_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
QUERY_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")


def make_user(**overrides: Any) -> User:
    data: dict[str, Any] = {
        "id": USER_ID,
        "email": "ada@example.com",
        "password_hash": "hashed-password",
        "name": "Ada Lovelace",
        "created_at": NOW,
    }
    data.update(overrides)
    return User(**data)


def make_collection(**overrides: Any) -> Collection:
    data: dict[str, Any] = {
        "id": COLLECTION_ID,
        "user_id": USER_ID,
        "name": "Policies",
        "description": "Company policies",
        "chroma_collection_id": f"col_{COLLECTION_ID}",
        "created_at": NOW,
    }
    data.update(overrides)
    return Collection(**data)


def make_document(**overrides: Any) -> Document:
    data: dict[str, Any] = {
        "id": DOCUMENT_ID,
        "collection_id": COLLECTION_ID,
        "filename": "policy.pdf",
        "file_type": FileType.PDF,
        "status": DocumentStatus.READY,
        "chunk_count": None,
        "error_message": None,
        "created_at": NOW,
    }
    data.update(overrides)
    return Document(**data)


def make_history(**overrides: Any) -> QueryHistory:
    data: dict[str, Any] = {
        "id": QUERY_ID,
        "collection_id": COLLECTION_ID,
        "user_id": USER_ID,
        "question": "What is the remote work policy?",
        "answer": "Remote work is allowed on Fridays.",
        "citations": [{"filename": "policy.pdf", "chunk_index": 1, "relevance_score": 0.9}],
        "created_at": NOW,
    }
    data.update(overrides)
    return QueryHistory(**data)


def scalar_result(value: Any) -> MagicMock:
    """Mimic a SQLAlchemy result whose scalar and first() return one row."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    scalars = MagicMock()
    scalars.first.return_value = value
    scalars.all.return_value = [] if value is None else [value]
    result.scalars.return_value = scalars
    return result


def rows_result(rows: list[Any]) -> MagicMock:
    """Mimic a SQLAlchemy result whose scalars().all() returns rows."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = rows[0] if rows else None
    scalars = MagicMock()
    scalars.all.return_value = rows
    scalars.first.return_value = rows[0] if rows else None
    result.scalars.return_value = scalars
    return result


class SessionContext:
    """Async context manager wrapping a mock session, like async_sessionmaker()."""

    def __init__(self, session: AsyncMock) -> None:
        self.session = session

    async def __aenter__(self) -> AsyncMock:
        return self.session

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False
