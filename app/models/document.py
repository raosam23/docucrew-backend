from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey
from sqlalchemy.sql import func
from sqlmodel import Field, SQLModel


class FileType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MD = "md"

class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"

class Document(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    collection_id: UUID = Field(sa_column=Column[Any](ForeignKey("collection.id", ondelete="CASCADE"), nullable=False, index=True))
    filename: str
    file_type: FileType = Field(
        sa_column=Column[Any](
            SAEnum(FileType, values_callable=lambda x: [e.value for e in x]),
            nullable=False
        )
    )
    status: DocumentStatus = Field(
        sa_column=Column[Any](
            SAEnum(DocumentStatus, values_callable=lambda x: [e.value for e in x]),
            nullable=False
        )
    )
    chunk_count: Optional[int] = Field(default=None, nullable=True)
    error_message: Optional[str] = Field(default=None, nullable=True)
    created_at: datetime = Field(sa_column=Column[Any](
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    ))