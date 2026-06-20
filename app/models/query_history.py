from datetime import datetime
from typing import Any, List
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlmodel import Field, SQLModel


class QueryHistory(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, index=True, primary_key=True)
    collection_id: UUID = Field(sa_column=Column[Any](ForeignKey("collection.id", ondelete="CASCADE"), nullable=False, index=True))
    user_id: UUID = Field(sa_column=Column[Any](ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True))
    question: str = Field(sa_column=Column[Any](Text))
    answer: str = Field(sa_column=Column[Any](Text))
    citations: List[Any] = Field(default_factory=list, sa_column=Column[Any](JSONB, nullable=False))
    created_at: datetime = Field(sa_column=Column[Any](
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    ))
    