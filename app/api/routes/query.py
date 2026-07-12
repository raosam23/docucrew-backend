import json
from json import JSONDecodeError
from typing import Any, Dict, Generator, List, Tuple, cast
from uuid import UUID

import anyio
from crewai.types.streaming import CrewStreamingOutput
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import desc, select

from app.core.security import get_current_user
from app.crews.query.crew import (ANSWER_STREAM_CITATION_MARKER,
                                  ANSWER_STREAM_START_MARKER, build_query_crew)
from app.db.database import async_session_maker, get_session
from app.models.collection import Collection
from app.models.document import Document, DocumentStatus
from app.models.query_history import QueryHistory
from app.models.user import User
from app.schemas.query import (QueryAnswer, QueryHistoryResponse, QueryRequest,
                               QueryResponse)

router = APIRouter()

def format_sse(event: str, data: Dict[str, Any]) -> str:
    """Format data for Server-Sent Events (SSE)
    Args:
        event: The event name
        data: The data to send
    Returns:
        A string formatted for SSE
    """
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"

ANSWER_WRAPPERS = (
    ANSWER_STREAM_START_MARKER,
    "Final answer:",
    "Final Answer:",
    "I now can give a great answer.",
    "I now can give a great answer",
    "Here is my answer:",
    "Here is the answer:",
    "Here is the final answer:",
    "Here is the great answer:",
    "Here is the great final answer:",
    "Here is the great final answer.",
)
_LONGEST_WRAPPER = max(len(wrapper) for wrapper in ANSWER_WRAPPERS)
_CITATION_MARKER_LENGTH = len(ANSWER_STREAM_CITATION_MARKER)
_REACT_HINTS = ("Action:", "Action Input:", "Thought:")
_FALLBACK_TOKEN_SIZE = 8

def strip_answer_wrappers(text: str) -> Tuple[bool, str]:
    """Remove CrewAI boilerplate wrappers.
    Args:
        text: The text to strip
    Returns:
        Tuple[bool, str]: A tuple containing a boolean indicating if any wrappers were found and the stripped text
    """
    found = False
    while True:
        stripped = text.lstrip(" \t\r\n")
        matched = False
        for wrapper in sorted(ANSWER_WRAPPERS, key=len, reverse=True):
            if stripped.startswith(wrapper):
                text=stripped[len(wrapper):]
                found = True
                matched = True
                break
        if matched:
            continue

        earliest: Tuple[int, int] | None = None
        for wrapper in ANSWER_WRAPPERS:
            index = text.find(wrapper)
            if index < 0:
                continue
            if earliest is None:
                earliest = (index, len(wrapper))
            elif index < earliest[0]:
                earliest = (index, len(wrapper))
        if earliest is None:
            break
        text = text[earliest[0] + earliest[1]:]
        found = True
    return found, text.lstrip(" \t\r\n")

def should_force_answer_start(pending: str) -> bool:
    """If synthesizer wrote proceed and no ReAct/tool markers, treat it as answer.
    Args:
        pending: The pending text to check
    Returns:
        True if the pending text should be treated as an answer, False otherwise
    """
    if len(pending.strip()) <  40:
        return False
    return not any(hint in pending for hint in _REACT_HINTS)

def iter_fallback_tokens(text: str) -> Generator[str, None, None]:
    """Split a late answer into small chunks so clients never see one giant token.
    Args:
        text: The text to split
    Returns:
        A generator of strings, each representing a small chunk of the text
    """
    text = text.strip()
    if not text:
        return
    index = 0
    while index < len(text):
        yield text[index: index + _FALLBACK_TOKEN_SIZE]
        index += _FALLBACK_TOKEN_SIZE

def clean_stream_answer(answer: str) -> str:
    """Clean a stream answer by removing boilerplate wrappers.
    Args:
        answer: The answer to clean
    Returns:
        The cleaned answer
    """
    _, answer = strip_answer_wrappers(answer)
    citation_index = answer.find(ANSWER_STREAM_CITATION_MARKER)
    if citation_index >= 0:
        answer = answer[:citation_index]
    return answer.strip()

def parse_stream_citations(citation_text: str) -> List[Dict[str, Any]]:
    citation_text = citation_text.strip()
    if not citation_text:
        return []

    try:
        parsed, _ = json.JSONDecoder().raw_decode(citation_text)
    except JSONDecodeError:
        bracket = citation_text.find("[")
        if bracket < 0:
            return []
        
        try:
            parsed, _ = json.JSONDecoder().raw_decode(citation_text[bracket:])
        except JSONDecodeError:
            return []
        
    if not isinstance(parsed, list):
        return []
    
    citations = []
    for item in parsed:
        if isinstance(item, dict) and "filename" in item:
            citations.append(
                {
                    "filename": item.get("filename"),
                    "chunk_index": item.get("chunk_index", 0),
                    "relevance_score": item.get("relevance_score", 0.0)
                }
            )
    return citations

async def save_query_history(
    collection_id: UUID,
    user_id: UUID,
    question: str,
    answer: str,
    citations: List[Dict[str, Any]],
) -> QueryHistory:
    async with async_session_maker() as session:
        history = QueryHistory(
            collection_id=collection_id,
            user_id=user_id,
            question=question,
            answer=answer,
            citations=citations,
        )
        session.add(history)
        await session.commit()
        await session.refresh(history)
        return history 

@router.post("/{collection_id}/query", status_code=status.HTTP_200_OK, response_model=QueryResponse)
async def query_collection(collection_id: UUID, request: QueryRequest, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    response = await session.execute(select(Collection).where(Collection.id == collection_id,Collection.user_id == user.id))
    collections = response.scalar_one_or_none()
    if not collections:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collections not found")
    documents_response = await session.execute(select(Document).where(Document.collection_id == collection_id))
    documents = documents_response.scalars().all()
    for document in documents:
        if document.status != DocumentStatus.READY:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Document '{document.filename}' is not ready (status: {document.status})")
    query_history_response = await session.execute(select(QueryHistory).where(QueryHistory.collection_id == collection_id).order_by(desc(QueryHistory.created_at)).limit(5))
    query_history = query_history_response.scalars().all()
    chat_history = ""
    for item in query_history:
        chat_history += f"\n\nQuestion: {item.question}\nAnswer: {item.answer}"
    query_crew, synthesize_task = build_query_crew()
    query_crew.kickoff(inputs={"question": request.question, "collection_id": collections.chroma_collection_id, "chat_history": chat_history})
    task_output = synthesize_task.output
    if task_output is None or task_output.pydantic is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to synthesize answer",
        )
    structured = cast(QueryAnswer, task_output.pydantic)
    answer = structured.answer
    citations = [c.model_dump() for c in structured.citations]

    history = QueryHistory(
        collection_id=collection_id,
        user_id=user.id,
        question=request.question,
        answer=answer,
        citations=citations,
    )

    session.add(history)
    await session.commit()
    await session.refresh(history)

    response = QueryResponse(
        answer=history.answer,
        citations = history.citations,
        query_id=history.id
    )

    return response


@router.get("/{collection_id}/history", status_code=status.HTTP_200_OK, response_model=List[QueryHistoryResponse])
async def get_query_history(collection_id: UUID, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    collection_response = await session.execute(select(Collection).where(Collection.id==collection_id, Collection.user_id == user.id))
    collection = collection_response.scalar_one_or_none()
    if not collection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    history_response = await session.execute(select(QueryHistory).where(QueryHistory.collection_id == collection_id))
    histories = history_response.scalars().all()
    return [QueryHistoryResponse.model_validate(history) for history in histories]

@router.post("/{collection_id}/query/stream", status_code=status.HTTP_200_OK)
async def stream_query_collection(
    collection_id: UUID,
    request: QueryRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    response = await session.execute(
        select(Collection).where(
            Collection.id == collection_id,
            Collection.user_id == user.id,
        )
    )
    collection = response.scalar_one_or_none()
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found",
        )
    documents_response = await session.execute(
        select(Document).where(Document.collection_id == collection_id)
    )
    documents = documents_response.scalars().all()
    for document in documents:
        if document.status != DocumentStatus.READY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document '{document.filename}' is not ready (status: {document.status})",
            )
    query_history_response = await session.execute(
        select(QueryHistory)
        .where(QueryHistory.collection_id == collection_id)
        .order_by(desc(QueryHistory.created_at))
        .limit(5)
    )
    query_history = query_history_response.scalars().all()
    chat_history = ""
    for item in query_history:
        prior_answer = (item.answer or "")[:500]
        chat_history += f"\n\nQuestion: {item.question}\nAnswer: {prior_answer}"

    def event_generator() -> Generator[str, None, None]:
        answer = ""
        pending = ""
        full_text = ""
        citation_text = ""
        answer_started = False
        citations_started = False

        def emit_token(text: str) -> Generator[str, None, None]:
            nonlocal answer
            if not text:
                return
            answer += text
            yield format_sse("token", {"content": text})

        try:
            yield format_sse("status", {"message": "started"})

            query_crew, _ = build_query_crew(stream=True)
            stream_output = query_crew.kickoff(
                inputs={
                    "question": request.question,
                    "collection_id": collection.chroma_collection_id,
                    "chat_history": chat_history,
                }
            )
            if not isinstance(stream_output, CrewStreamingOutput):
                raise RuntimeError("Expected streaming output from crew kickoff")

            for chunk in stream_output:
                if getattr(chunk, "agent_role", "") != "SynthesizerAgent":
                    continue
                if getattr(chunk, "chunk_type", None) and getattr(chunk.chunk_type, "value", "") != "text":
                    continue

                content = str(chunk.content or "")
                if not content:
                    continue

                full_text += content

                if citations_started:
                    citation_text += content
                    continue

                pending += content

                if not answer_started:
                    found, remainder = strip_answer_wrappers(pending)
                    if not found and not should_force_answer_start(pending):
                        if len(pending) > _LONGEST_WRAPPER:
                            pending = pending[-(_LONGEST_WRAPPER - 1) :]
                        continue
                    if found:
                        pending = remainder
                    answer_started = True
                    if not pending:
                        continue

                # Keep stripping wrappers after preamble (e.g. "Final Answer:").
                if not answer:
                    _, pending = strip_answer_wrappers(pending)
                    pending = pending.lstrip(" \t\r\n")
                    if not pending:
                        continue
                    if any(
                        wrapper.startswith(pending) and pending != wrapper
                        for wrapper in ANSWER_WRAPPERS
                    ):
                        continue

                marker_index = pending.find(ANSWER_STREAM_CITATION_MARKER)
                if marker_index >= 0:
                    visible = pending[:marker_index]
                    citation_text += pending[marker_index + _CITATION_MARKER_LENGTH :]
                    pending = ""
                    citations_started = True
                    yield from emit_token(visible)
                    continue

                safe_length = max(0, len(pending) - _CITATION_MARKER_LENGTH + 1)
                if safe_length == 0:
                    continue

                visible = pending[:safe_length]
                pending = pending[safe_length:]
                yield from emit_token(visible)

            if pending and answer_started and not citations_started:
                yield from emit_token(pending)
                pending = ""

            if not answer_started:
                fallback_answer = full_text
                fallback_marker_index = fallback_answer.find(ANSWER_STREAM_CITATION_MARKER)
                if fallback_marker_index >= 0:
                    citation_text += fallback_answer[
                        fallback_marker_index + _CITATION_MARKER_LENGTH :
                    ]
                    fallback_answer = fallback_answer[:fallback_marker_index]
                fallback_answer = clean_stream_answer(fallback_answer)
                for piece in iter_fallback_tokens(fallback_answer):
                    yield from emit_token(piece)

            answer = clean_stream_answer(answer)
            if not citation_text and ANSWER_STREAM_CITATION_MARKER in full_text:
                citation_text = full_text.split(ANSWER_STREAM_CITATION_MARKER, 1)[1]
            citations = parse_stream_citations(citation_text)
            history = anyio.from_thread.run(
                save_query_history,
                collection_id,
                user.id,
                request.question,
                answer,
                citations,
            )

            yield format_sse(
                "done",
                {
                    "query_id": str(history.id),
                    "answer": history.answer,
                    "citations": history.citations,
                    "created_at": history.created_at.isoformat(),
                },
            )
        except Exception as error:
            yield format_sse("error", {"message": str(error)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
