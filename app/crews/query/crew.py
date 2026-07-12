from typing import Tuple

from crewai import LLM, Agent, Crew, Process, Task

from app.core.config import settings
from app.crews.query.agents import (create_cross_reference_agent,
                                    create_gap_analyst_agent,
                                    create_retriever_agent,
                                    create_synthesizer_agent)
from app.schemas.query import QueryAnswer

ANSWER_STREAM_START_MARKER = "FINAL_ANSWER_START"
ANSWER_STREAM_CITATION_MARKER = "__CITATIONS_JSON__"


def create_manager_agent() -> Agent:
    """Create a manager agent."""
    return Agent(
        role="Manager",
        goal="Your job is to manage the crew and delegate tasks to the right agent.",
        backstory="You are a manager who delegates tasks based on the question type.",
        llm=LLM(settings.OPENAI_MODEL),
        tools=[],
        allow_delegation=True,
    )


def build_query_crew(stream: bool = False) -> Tuple[Crew, Task]:
    """Build a query crew.

    Args:
        stream: Whether to stream the answer. Default is False.

    Returns:
        The Crew and the synthesize Task (needed to read structured output / stream parsing).
    """
    retriever_agent = create_retriever_agent()
    cross_reference_agent = create_cross_reference_agent()
    synthesizer_agent = create_synthesizer_agent(include_web_search=not stream)
    gap_analyst_agent = create_gap_analyst_agent()

    retrieve_task = Task(
        description="Retrieve top-k relevant chunks from Chroma DB collection {collection_id} for the user question: {question}. Each chunk has metadata containing: doc_id, filename, file_type, chunk_index, page_number, collection_id. Always extract and pass the 'filename' field from metadata for use in citations. Here is the last 5 conversation for your reference: {chat_history}",
        expected_output="A list of relevent chunks with text, metadata and distance score",
        agent=retriever_agent,
    )

    cross_reference_task = Task(
        description="Analyse the retrieved chunks across documents. Identify agreements and contradictions.",
        expected_output="A summary of arguments and contradcitions found across the retrieved chunks",
        agent=cross_reference_agent,
        context=[retrieve_task],
    )

    gap_analyst_task = Task(
        description="Identify what information is missing or contradictory in the document for the question: {question}",
        expected_output="A summary of gaps and conflicts found in the documents",
        agent=gap_analyst_agent,
        context=[retrieve_task],
    )

    if stream:
        synthesize_task = Task(
            description=(
                "Produce the final answer for the question: {question}. "
                "Write a clear user-facing answer. Cite source filenames and chunk numbers naturally when useful. "
                f"After the answer text, on a new line write exactly {ANSWER_STREAM_CITATION_MARKER} "
                "followed immediately by a JSON array of citations. Each citation must use the exact filename "
                'from retrieved chunk metadata and this shape: {"filename": "exact filename", "chunk_index": 0, "relevance_score": 0.0}. '
                "Here is the last 5 conversation for your reference: {chat_history}"
            ),
            expected_output=(
                f"Plain answer text then a line with {ANSWER_STREAM_CITATION_MARKER}"
                '[{"filename": "file.pdf", "chunk_index": 0, "relevance_score": 0.9}]'
            ),
            agent=synthesizer_agent,
            context=[retrieve_task, cross_reference_task],
        )
        crew = Crew(
            agents=[
                retriever_agent,
                cross_reference_agent,
                synthesizer_agent,
                gap_analyst_agent,
            ],
            tasks=[
                retrieve_task,
                cross_reference_task,
                synthesize_task,
                gap_analyst_task,
            ],
            process=Process.sequential,
            stream=True,
        )
    else:
        synthesize_task = Task(
            description="Produce the final structured answer for the question: {question}. You MUST return ONLY a valid JSON object with no additional text, no markdown, no code blocks. The 'filename' in citations MUST be the exact filename from the retrieved chunk metadata, do NOT use placeholders like '...' or made up names. Return exactly: {\"answer\": \"your answer here\", \"citations\": [{\"filename\": \"exact filename from metadata\", \"chunk_index\": 0, \"relevance_score\": 0.0}]} Here is the last 5 conversation for your reference: {chat_history}",
            expected_output="""A raw JSON string with no Markdown, no code blocks, just valid JSON in this exact format:
{
    "answer": "...",
    "citations": [
        {"filename": "...", "chunk_index": 0, "relevance_score": 0.0}
    ]
}""",
            agent=synthesizer_agent,
            context=[retrieve_task, cross_reference_task],
            output_pydantic=QueryAnswer,
        )
        crew = Crew(
            agents=[
                retriever_agent,
                cross_reference_agent,
                synthesizer_agent,
                gap_analyst_agent,
            ],
            tasks=[
                retrieve_task,
                cross_reference_task,
                synthesize_task,
                gap_analyst_task,
            ],
            process=Process.hierarchical,
            manager_agent=create_manager_agent(),
            stream=False,
        )

    return crew, synthesize_task
