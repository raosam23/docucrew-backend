from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, Enum as SAEnum
from sqlalchemy.sql import func
from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional
from enum import Enum

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
    collection_id: UUID = Field(foreign_key="collection.id", index=True)
    filename: str
    file_type: FileType = Field(
        sa_column=Column(
            SAEnum(FileType, values_callable=lambda x: [e.value for e in x]),
            nullable=False
        )
    )
    status: DocumentStatus = Field(
        sa_column=Column(
            SAEnum(DocumentStatus, values_callable=lambda x: [e.value for e in x]),
            nullable=False
        )
    )
    chunk_count: Optional[int] = Field(default=None, nullable=True)
    error_message: Optional[str] = Field(default=None, nullable=True)
    created_at: datetime = Field(sa_column=Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    ))