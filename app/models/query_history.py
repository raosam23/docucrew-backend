from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field
from sqlalchemy.sql import func
from sqlalchemy import Column, DateTime, Text
from typing import List, Any
from datetime import datetime

from uuid import UUID, uuid4

class QueryHistory(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, index=True, primary_key=True)
    collection_id: UUID = Field(foreign_key="collection.id", index=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    question: str = Field(sa_column=Column(Text))
    answer: str = Field(sa_column=Column(Text))
    citations: List[Any] = Field(default_factory=list, sa_column=Column(JSONB, nullable=False))
    created_at: datetime = Field(sa_column=Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    ))
    