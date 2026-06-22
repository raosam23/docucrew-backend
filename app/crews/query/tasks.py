from crewai import Task

from app.crews.query.agents import (cross_reference_agent, gap_analyst_agent,
                                    retriever_agent, synthesizer_agent)
from app.schemas.query import QueryAnswer

retrieve_task = Task(
    description="Retrieve top-k relevant chunks from Chroma DB collection {collection_id} for the user question: {question}",
    expected_output="A list of relevent chunks with text, metadata and distance score",
    agent=retriever_agent
)

cross_reference_task = Task(
    description="Analyse the retrieved chunks across documents. Identify agreements and contradictions.",
    expected_output="A summary of arguments and contradcitions found across the retrieved chunks",
    agent=cross_reference_agent,
    context=[retrieve_task],
)

synthesize_task = Task(
    description="Produce the final structured answer for the question: {question}. You MUST return ONLY a valid JSON object with no additional text, no markdown, no code blocks. Return exactly: {\"answer\": \"your answer here\", \"citations\": [{\"filename\": \"...\", \"chunk_index\": 0, \"relevance_score\": 0.0}]}",
    expected_output="""A raw JSON string with no Markdown, no code blocks, just valid JSON in this exact format:
{
    "answer": "...",
    "citations": [
        {"filename": "...", "chunk_index": 0, "relevance_score": 0.0}
    ]
}""",
    agent=synthesizer_agent,
    context=[retrieve_task],
    output_pydantic=QueryAnswer,
)

gap_analyst_task = Task(
    description="Identify what information is missing or contradictory in the document for the question: {question}",
    expected_output="A summary of gaps and conflicts found in the documents",
    agent=gap_analyst_agent,
    context=[retrieve_task]
)
