from crewai import Task

from app.crews.query.agents import (
    retriever_agent,
    cross_reference_agent,
    synthesizer_agent,
    gap_analyst_agent,
)

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
    description="Produce the final structured answer with citations for the question: {question}",
    expected_output="A JSON object with answer (str) and citations (list of filename, chunk_index, relevance_score)",
    agent=synthesizer_agent,
    context=[retrieve_task],
)

gap_analyst_task = Task(
    description="Identify what information is missing or contradictory in the document for the question: {question}",
    expected_output="A summary of gaps and conflicts found in the documents",
    agent=gap_analyst_agent,
    context=[retrieve_task]
)
