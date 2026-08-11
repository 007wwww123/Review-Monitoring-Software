from datetime import datetime
from uuid import UUID
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
