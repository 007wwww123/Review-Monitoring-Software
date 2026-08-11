from datetime import datetime
from uuid import UUID
from typing import Literal
from pydantic import Field
from .common import StrictModel

class LoginRequest(StrictModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)

class LoginResponse(StrictModel):
    user_id: int
    username: str
    role: str
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime

class CurrentUserResponse(StrictModel):
    user_id: int
    username: str
    display_name: str | None
    role: str
    status: str
    last_login_at: datetime | None

class PasswordChangeRequest(StrictModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)

class UserCreateRequest(StrictModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=256)
    role: Literal["reviewer", "operator"]

class UserResponse(StrictModel):
    user_id: int
    username: str
    display_name: str | None
    role: str
    status: str
    created_at: datetime
