"""Query crew factories and the legacy task module. No crew is kicked off."""

import os

from crewai import Process
from crewai_tools import TavilySearchTool

from app.core.config import settings
from app.crews.query.agents import (
    create_cross_reference_agent,
    create_gap_analyst_agent,
    create_retriever_agent,
    create_synthesizer_agent,
    cross_reference_agent,
    gap_analyst_agent,
    retriever_agent,
    synthesizer_agent,
)
from app.crews.query.crew import (
    ANSWER_STREAM_CITATION_MARKER,
    ANSWER_STREAM_START_MARKER,
    build_query_crew,
)
from app.crews.query.tasks import (
    cross_reference_task,
    gap_analyst_task,
    retrieve_task,
    synthesize_task,
)
from app.crews.tools import ChromaSearchTool
from app.schemas.query import QueryAnswer


def test_query_agent_factories_attach_the_expected_tools() -> None:
    retriever = create_retriever_agent()
    cross = create_cross_reference_agent()
    synthesizer = create_synthesizer_agent()
    quiet_synthesizer = create_synthesizer_agent(include_web_search=False)
    gap = create_gap_analyst_agent()

    assert [type(tool) for tool in retriever.tools] == [ChromaSearchTool]
    assert cross.tools == []
    assert [type(tool) for tool in synthesizer.tools] == [TavilySearchTool]
    assert quiet_synthesizer.tools == []
    assert [type(tool) for tool in gap.tools] == [ChromaSearchTool, TavilySearchTool]
    assert retriever.llm.model == settings.OPENAI_MODEL
    assert retriever.role == "RetrieverAgent"
    assert cross.role == "CrossReferenceAgent"
    assert synthesizer.role == "SynthesizerAgent"
    assert gap.role == "GapAnalystAgent"
    assert os.environ["TAVILY_API_KEY"] == settings.TAVILY_API_KEY


def test_module_level_query_agents_match_the_factories() -> None:
    assert isinstance(retriever_agent.tools[0], ChromaSearchTool)
    assert cross_reference_agent.tools == []
    assert isinstance(synthesizer_agent.tools[0], TavilySearchTool)
    assert [type(tool) for tool in gap_analyst_agent.tools] == [ChromaSearchTool, TavilySearchTool]


def test_legacy_tasks_are_wired_to_the_module_agents() -> None:
    assert retrieve_task.agent is retriever_agent
    assert cross_reference_task.agent is cross_reference_agent
    assert synthesize_task.agent is synthesizer_agent
    assert gap_analyst_task.agent is gap_analyst_agent
    assert cross_reference_task.context == [retrieve_task]
    assert synthesize_task.context == [retrieve_task]
    assert gap_analyst_task.context == [retrieve_task]
    assert synthesize_task.output_pydantic is QueryAnswer
    assert "{collection_id}" in retrieve_task.description
    assert "{question}" in synthesize_task.description


def test_hierarchical_query_crew_uses_a_manager_and_structured_output() -> None:
    crew, task = build_query_crew()

    assert crew.process == Process.hierarchical
    assert crew.stream is False
    assert crew.manager_agent is not None
    assert crew.manager_agent.role == "Manager"
    assert crew.manager_agent.allow_delegation is True
    assert crew.manager_agent.llm.model == settings.OPENAI_MODEL
    assert [agent.role for agent in crew.agents] == [
        "RetrieverAgent",
        "CrossReferenceAgent",
        "SynthesizerAgent",
        "GapAnalystAgent",
    ]
    retrieve, cross, synthesize, gap = crew.tasks
    assert cross.context == [retrieve]
    assert synthesize.context == [retrieve, cross]
    assert gap.context == [retrieve]
    assert synthesize.output_pydantic is QueryAnswer
    assert task is synthesize
    assert [type(tool) for tool in synthesize.agent.tools] == [TavilySearchTool]
    assert [type(tool) for tool in gap.agent.tools] == [ChromaSearchTool, TavilySearchTool]


def test_streaming_query_crew_is_sequential_and_skips_web_search() -> None:
    crew, task = build_query_crew(stream=True)

    assert crew.process == Process.sequential
    assert crew.stream is True
    assert crew.manager_agent is None
    retrieve, cross, synthesize, gap = crew.tasks
    assert task is synthesize
    assert synthesize.output_pydantic is None
    assert synthesize.agent.tools == []
    assert synthesize.context == [retrieve, cross]
    assert gap.context == [retrieve]
    assert (
        ANSWER_STREAM_START_MARKER in synthesize.description or ANSWER_STREAM_CITATION_MARKER in synthesize.description
    )
    assert ANSWER_STREAM_CITATION_MARKER in synthesize.description
    assert ANSWER_STREAM_CITATION_MARKER in synthesize.expected_output
