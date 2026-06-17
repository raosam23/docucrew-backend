from crewai import Task

from app.crews.ingestion.agents import (chunker_and_embedder_agent,
                                        document_parser_agent,
                                        document_tagger_agent)

parse_documents_task = Task(
    description="Given file paths: {files}, parse all uploaded files and return a list of {doc_id, filename, text}",
    expected_output="A list of dictionaries, each containing the document ID, filename, and text content.",
    agent=document_parser_agent,
)

chunk_and_embed_task = Task(
    description="Given the parsed text list, chunk each document and embed all chunks into ChromaDB collection: {collection_id}. Return {doc_id, chunk_count} for each",
    expected_output="A list of dictionaries, each containing the document ID, chunk count and chunk metadata.",
    agent=chunker_and_embedder_agent,
    context=[parse_documents_task]
)

tag_documents_task = Task(
    description="Given a 500-character sample of each document's text, classify each document and return tags",
    expected_output="A list of dictionaries, each containing the document ID, domain, type and key topics.",
    agent=document_tagger_agent,
    context=[parse_documents_task],
)