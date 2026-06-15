from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.security import get_current_user
from app.db.database import get_session
from app.models.collection import Collection
from app.models.user import User
from app.schemas.collection import CollectionCreate, CollectionResponse
from app.services.chroma_service import delete_collection

router = APIRouter()

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=CollectionResponse)
async def create_collection(
    collection: CollectionCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)):
    """Endpoint that creates Collection object and stores it in the database"""
    collection = Collection(
        user_id = user.id,
        name = collection.name,
        description = collection.description,
    )
    chroma_collection_id = f"col_{collection.id}"
    collection.chroma_collection_id = chroma_collection_id
    session.add(collection)
    await session.commit()
    await session.refresh(collection)
    return CollectionResponse.model_validate(collection)

@router.get("/", status_code=status.HTTP_200_OK, response_model=List[CollectionResponse])
async def get_all_collections(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    """Endpoint that retrieves all collections for a user"""
    response = await session.execute(select(Collection).where(Collection.user_id == user.id))
    collections = response.scalars().all()
    return [CollectionResponse.model_validate(collection) for collection in collections]

@router.get("/{collection_id}", status_code=status.HTTP_200_OK, response_model=CollectionResponse)
async def get_collection_by_id(
    collection_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)):
    """Endpoint that retrieves a collection by its ID"""
    response = await session.execute(
        select(Collection)
        .where(Collection.id == collection_id, Collection.user_id == user.id))
    collection = response.scalar_one_or_none()
    if not collection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    return CollectionResponse.model_validate(collection)

@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection_by_id(
    collection_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)):
    """Endpoint that deletes a collection by its ID"""
    response = await session.execute(
        select(Collection)
        .where(Collection.id == collection_id, Collection.user_id == user.id))
    collection = response.scalar_one_or_none()
    if not collection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    delete_collection(collection.chroma_collection_id)
    await session.delete(collection)
    await session.commit()
