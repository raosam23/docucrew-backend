from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CollectionCreate(BaseModel):
    """Schema of what the user sends to create a collection"""
    name: str = Field(description="The name of the collection")
    description: Optional[str] = Field(default=None, description="The description of the collection")

class CollectionResponse(BaseModel):
    """Schema of what the API returns for a collection"""
    model_config = ConfigDict(from_attributes=True)
    id: UUID = Field(description="The unique ID of a collection")
    user_id: UUID = Field(description="The unique ID of the user who owns the collection")
    name: str = Field(description="The name of the collection")
    description: Optional[str] = Field(default=None, description="The description of the collection")
    chroma_collection_id: str = Field(description="The unique ID of the collection in Chroma DB")
    created_at: datetime = Field(description="The time at which the collection was created")
    