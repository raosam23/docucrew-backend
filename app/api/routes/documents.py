import os
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.security import get_current_user
from app.db.database import get_session
from app.models.collection import Collection
from app.models.document import Document, DocumentStatus, FileType
from app.models.user import User
from app.schemas.document import DocumentResponse
from app.services.chroma_service import delete_chunks_by_doc_id

router = APIRouter()

@router.post("/{collection_id}/documents/", response_model=List[DocumentResponse])
async def upload_documents(
    collection_id: UUID,
    files: List[UploadFile] = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Endpoint that uploads multiple documents to a collection"""
    response = await session.execute(select(Collection).where(Collection.id == collection_id, Collection.user_id == user.id))
    collection = response.scalar_one_or_none()
    if not collection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    all_documents: List = []
    for file in files:
        ext = file.filename.split(".")[-1].lower()
        if ext not in [e.value for e in FileType]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid file type {file.filename}")
        if file.size > 10 * 1024 * 1024:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"File {file.filename} is too large")
        file_path = f"./uploads/{collection_id}/{file.filename}"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
        document = Document(
            collection_id=collection_id,
            filename=file.filename,
            file_type=FileType(file.filename.split(".")[-1].lower()),
            status=DocumentStatus.PENDING,
        )
        session.add(document)
        all_documents.append(document)
    await session.commit()
    for document in all_documents:
        await session.refresh(document)
    return [DocumentResponse.model_validate(document) for document in all_documents]

@router.get("/{collection_id}/documents", response_model=List[DocumentResponse], status_code=status.HTTP_200_OK)
async def get_documents_by_collection_id(collection_id: UUID, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    """Endpoint that retrieves all documents in a collection"""
    response = await session.execute(select(Collection).where(Collection.id == collection_id, Collection.user_id == user.id))
    collection = response.scalar_one_or_none()
    if not collection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    response = await session.execute(select(Document).where(Document.collection_id == collection_id))
    documents = response.scalars().all()
    return [DocumentResponse.model_validate(document) for document in documents]

@router.delete("/{collection_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document_by_ids(collection_id: UUID, document_id: UUID, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    response = await session.execute(select(Collection).where(Collection.id == collection_id, Collection.user_id == user.id))
    collection = response.scalar_one_or_none()
    if not collection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    response = await session.execute(select(Document).where(Document.id == document_id, Document.collection_id == collection_id))
    document = response.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if document.status == DocumentStatus.PROCESSING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document is being processed")
    file_path = f"./uploads/{collection_id}/{document.filename}"
    if os.path.exists(file_path):
        os.remove(file_path)
    delete_chunks_by_doc_id(collection.chroma_collection_id, str(document.id))
    await session.delete(document)
    await session.commit()
