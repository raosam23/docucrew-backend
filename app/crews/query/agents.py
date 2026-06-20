from crewai import Agent

from app.core.config import settings
from app.crews.tools import ChromaSearchTool

retriever_agent = Agent(
    role="RetrieverAgent",
    goal="Search the vector store for the most relevant chunks related to the user's question.",
    backstory="You are an expert at semantic search. Given a question, you retrieve the top-k most relevant document chunks from the vector store, alone with their source metata and relevance scores.",
    tools=[ChromaSearchTool()],
    llm=settings.OPENAI_MODEL,
)

cross_reference_agent = Agent(
    role="CrossReferenceAgent",
    goal="Find connections, contradictions and complementary information across mulitple retrived documents.",
    backstory="You are an expert at reading multiple text passages from different sources and identifying where thye agree, where they conflict and what each one adds to the others don't add.",
    tools=[],
    llm=settings.OPENAI_MODEL,
)

synthesizer_agent = Agent(
    role="SynthesizerAgent",
    goal="Produce a clear, well-cited final answer from the retrieved and cross-referenced evidence.",
    backstory="You are an expert at reading retrieved evidenceand crafting a coherant, accurate answer. ALways cite the source document and chunk for every claim made.",
    tools=[],
    llm=settings.OPENAI_MODEL,
)

gap_analyst_agent = Agent(
    role="GapAnalystAgent",
    goal="Identify what information is missin from the documents or where documents contradict each other.",
    backstory="You are an expert at reading a set of documents and spotting what is conspicously absent, where sources directly contradicts, and what questions the documents raise but do now answer.",
    tools=[ChromaSearchTool()],
    llm=settings.OPENAI_MODEL,
)