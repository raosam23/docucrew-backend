"""Ingestion crew wiring. Agents are constructed locally; nothing is kicked off."""

from crewai import Process

from app.core.config import settings
from app.crews.ingestion.agents import (
    chunker_and_embedder_agent,
    document_parser_agent,
    document_tagger_agent,
)
from app.crews.ingestion.crew import ingestion_crew
from app.crews.tools import ChromaStoreTool, FileReaderTool


def test_ingestion_agents_have_their_tools_and_model() -> None:
    assert isinstance(document_parser_agent.tools[0], FileReaderTool)
    assert isinstance(chunker_and_embedder_agent.tools[0], ChromaStoreTool)
    assert document_tagger_agent.tools == []
    assert document_parser_agent.llm.model == settings.OPENAI_MODEL
    assert chunker_and_embedder_agent.llm.model == settings.OPENAI_MODEL
    assert document_tagger_agent.llm.model == settings.OPENAI_MODEL
    assert document_parser_agent.role == "Document Parser"
    assert chunker_and_embedder_agent.role == "Text Chunker and Embedder"
    assert document_tagger_agent.role == "Document Analyst"


def test_ingestion_crew_runs_parse_then_chunk_then_tag() -> None:
    assert ingestion_crew.process == Process.sequential
    assert [agent.role for agent in ingestion_crew.agents] == [
        "Document Parser",
        "Text Chunker and Embedder",
        "Document Analyst",
    ]

    parse_task, chunk_task, tag_task = ingestion_crew.tasks
    assert parse_task.agent is document_parser_agent
    assert chunk_task.agent is chunker_and_embedder_agent
    assert tag_task.agent is document_tagger_agent
    assert chunk_task.context == [parse_task]
    assert tag_task.context == [parse_task]
    assert "{files}" in parse_task.description
    assert "{collection_id}" in chunk_task.description
    assert "domain" in tag_task.expected_output
