from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.security import (create_access_token, get_current_user,
                               hash_password, verify_password)
from app.db.database import get_session
from app.models.user import User
from app.schemas.auth import (LoginRequest, LoginResponse, RegisterRequest,
                              UserResponse)

router = APIRouter()

@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
async def register(register_request: RegisterRequest, session: AsyncSession = Depends(get_session)):
    """POST request endpoint to register the user to DocuCrew"""
    response = await session.execute(select(User).where(User.email == register_request.email))
    user = response.scalar_one_or_none()
    if user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")
    hashed_password = hash_password(register_request.password)
    user = User(
        email = register_request.email,
        password_hash = hashed_password,
        name = register_request.name
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return UserResponse.model_validate(user)

@router.post("/login", status_code=status.HTTP_200_OK, response_model = LoginResponse)
async def login(login_request: LoginRequest, session: AsyncSession = Depends(get_session)):
    """POST request endpoint to log the user in to DocuCrew"""
    response = await session.execute(select(User).where(User.email == login_request.email))
    user = response.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail = "Invalid credentials")
    if not verify_password(login_request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    access_token = create_access_token(
        data = {"sub": str(user.email)}
    )
    return({
        "access_token": access_token,
        "token_type": "bearer"
    })

@router.get("/me", status_code=status.HTTP_200_OK, response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    """GET request endpoint to get the current user"""
    return UserResponse.model_validate(user)
