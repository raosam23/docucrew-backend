from crewai import Crew, Process

from app.crews.ingestion.agents import chunker_and_embedder_agent, document_parser_agent, document_tagger_agent
from app.crews.ingestion.tasks import chunk_and_embed_task, parse_documents_task, tag_documents_task

ingestion_crew = Crew(
    agents=[document_parser_agent, chunker_and_embedder_agent, document_tagger_agent],
    tasks=[parse_documents_task, chunk_and_embed_task, tag_documents_task],
    process=Process.sequential,
)