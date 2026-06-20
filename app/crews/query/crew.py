from crewai import Crew, Process, LLM

from app.crews.query.agents import (
    retriever_agent,
    cross_reference_agent,
    synthesizer_agent,
    gap_analyst_agent
)

from app.core.config import settings

from app.crews.query.tasks import (
    retrieve_task,
    cross_reference_task,
    synthesize_task,
    gap_analyst_task
)

query_crew = Crew(
    agents=[retriever_agent, cross_reference_agent, synthesizer_agent, gap_analyst_agent],
    tasks=[retrieve_task, cross_reference_task, synthesize_task, gap_analyst_task],
    process=Process.hierarchical,
    manager_llm=LLM(model=settings.OPENAI_MODEL)
)