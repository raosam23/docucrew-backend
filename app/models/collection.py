from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy.sql import func
from sqlalchemy import Column, DateTime
from uuid import UUID, uuid4
from datetime import datetime

class Collection(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    user_id: UUID = Field(nullable=False, foreign_key="user.id")
    name: str
    description: Optional[str] = Field(default=None, nullable=True)
    chroma_collection_id: str
    created_at: datetime = Field(sa_column=Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    ))