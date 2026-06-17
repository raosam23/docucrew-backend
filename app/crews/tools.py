from typing import List, Type, Dict, Any
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from app.services.chroma_service import add_chunks
from app.services.file_service import parse_file

class ChromaStoreToolArgs(BaseModel):
    collection_id: str = Field(description="The ID of the collection to store the text chunk in.")
    chunks: List[Dict[str, Any]] = Field(description="The list of text chunks to store. Each chunk is a dictionary with the following keys: text (str) - The text chunk to store. metadata (dict) - The metadata for the text chunk.")

class FileReaderTool(BaseTool):
    name: str = "FileReaderTool"
    description: str = """Reads a file from disk and returns its plain text content. 
    Input: file_path (str) - The absolute path to the file to read.
    Output: text (str) - The plain text content of the file."""

    def _run(self, file_path: str) -> str:
        return parse_file(file_path)


class ChromaStoreTool(BaseTool):
    name: str = "ChromaStoreTool"
    description: str = "Stores a text chunk in ChromaDB. Input: collection_id (str) - The ID of the collection to store the text chunk in. text (str) - The text chunk to store. metadata (dict) - The metadata for the text chunk."
    args_schema: Type[BaseModel] = ChromaStoreToolArgs

    def _run(self, collection_id: str, chunks: List[Dict[str, Any]]) -> None:
        add_chunks(collection_id, chunks)