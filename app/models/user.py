from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime
from sqlalchemy.sql import func
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    email: str = Field(unique=True, nullable=False, index=True)
    password_hash: str
    name: Optional[str] = Field(default=None)
    created_at: datetime = Field(sa_column=Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    ))
