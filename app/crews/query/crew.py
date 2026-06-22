from crewai import LLM, Crew, Process, Agent

from app.core.config import settings
from app.crews.query.agents import (cross_reference_agent, gap_analyst_agent,
                                    retriever_agent, synthesizer_agent)
from app.crews.query.tasks import (cross_reference_task, gap_analyst_task,
                                   retrieve_task, synthesize_task)

manager_agent = Agent(
    role="Manager",
    goal="Your job is to manage the crew and delegate tasks to the right agent.",
    backstory="You are a manager who delegates tasks based on the question type.",
    llm=LLM(settings.OPENAI_MODEL),
    tools=[],
    allow_delegation=True,
)

query_crew = Crew(
    agents=[retriever_agent, cross_reference_agent, synthesizer_agent, gap_analyst_agent],
    tasks=[retrieve_task, cross_reference_task, synthesize_task, gap_analyst_task],
    process=Process.hierarchical,
    manager_agent=manager_agent,
)