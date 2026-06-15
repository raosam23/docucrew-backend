from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Citations(BaseModel):
    """Schema of the Citation that tha API returns"""
    filename: str = Field(description="The name of the cited file")
    chunk_index: int = Field(description="The index of the chunk in the cited file")
    relevance_score: Optional[float] = Field(default=None, description="The relevance score of the chunk")

class QueryRequest(BaseModel):
    """Schema of the query that the user sends"""
    question: str = Field(description="The question the user wants to ask")

class QueryResponse(BaseModel):
    """Schema of what the API returns for the query"""
    model_config = ConfigDict(from_attributes=True)
    answer: str = Field(description="The answer to the query")
    citations: Optional[List[Citations]] = Field(default=None, description="The citations for the query")
    query_id: UUID = Field(description="The unique ID of the query")
