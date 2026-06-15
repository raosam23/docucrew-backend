from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentStatus, FileType


class DocumentResponse(BaseModel):
    """Schema of what the API returns for a document"""
    model_config = ConfigDict(from_attributes=True)
    id: UUID = Field(description="The unique ID of the document")
    collection_id: UUID = Field(description="The unique ID of the collection the document belongs to")
    filename: str = Field(description="The name of the file")
    file_type: FileType = Field(description="The type of the file")
    status: DocumentStatus = Field(description="The status of the document")
    chunk_count: Optional[int] = Field(default=None, description="The count of chunks in the document")
    error_message: Optional[str] = Field(default=None, description="error message if any")
    created_at: datetime = Field(description="The time the document was created")