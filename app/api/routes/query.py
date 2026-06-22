from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.security import get_current_user
from app.crews.query.crew import query_crew
from app.crews.query.tasks import synthesize_task
from app.db.database import get_session
from app.models.collection import Collection
from app.models.document import Document, DocumentStatus
from app.models.query_history import QueryHistory
from app.models.user import User
from app.schemas.query import QueryAnswer, QueryHistoryResponse, QueryRequest, QueryResponse

router = APIRouter()

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

    query_crew.kickoff(inputs={"question": request.question, "collection_id": collections.chroma_collection_id})
    structured: QueryAnswer = synthesize_task.output.pydantic
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