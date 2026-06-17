from crewai import Agent

from app.crews.tools import ChromaStoreTool, FileReaderTool
from app.core.config import settings

document_parser_agent = Agent(
    role="Document Parser",
    goal="Extract clean plain text from uploaded files.",
    backstory="You are an expert at reading structured and unstructured documents and producing clean, readable text with preserved structure.",
    tools=[FileReaderTool()],
    llm=settings.OPENAI_MODEL,
)

chunker_and_embedder_agent = Agent(
    role="Text Chunker and Embedder",
    goal="Split extracted text into semantic chunks and embed them into ChromaDB with correct metadata.",
    backstory="You are an expert at splitting long documents into meaningful, overlapping chunks that preserve context, then storing them as vector embeddings for precise retrieval.",
    tools=[ChromaStoreTool()],
    llm=settings.OPENAI_MODEL,
)

document_tagger_agent = Agent(
    role="Document Analyst",
    goal="Identify the domain, type and key topics of the document and update its metadata.",
    backstory="You are an expert at quickly reading a document sample and producing a structured tag set: domain (legal, technical, medical, academic, general), document type (report, paper, contract, manual, notes), and key topics as a list.",
    tools=[],
    llm=settings.OPENAI_MODEL,
)