from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import datetime

class RegisterRequest(BaseModel):
    """Schema of what the user sends while registering"""
    email: str = Field(description="The email of the user trying to register to DocuCrew")
    password: str = Field(description="The password of the user trying to register to DocuCrew")
    name: Optional[str] = Field(default=None, description="The name of the user")

class LoginRequest(BaseModel):
    """Schema of what the user sends while logging in"""
    email: str = Field(description="The email of the user tring to log in to DocuCrew")
    password: str = Field(description="The password of the user trying to log in to DocuCrew")

class UserResponse(BaseModel):
    """Schema of what the API returns after register/login or /me"""
    model_config = ConfigDict(from_attributes=True)
    id: UUID = Field(description="The ID of the user")
    email: str = Field(description="The email of the user")
    name: Optional[str] = Field(default=None, description="The name of the user")
    created_at: datetime = Field(description="The time at which the user was created")
