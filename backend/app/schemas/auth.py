from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: "UserOut"


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    max_sessions: int

    model_config = {"from_attributes": True}


class SessionOut(BaseModel):
    id: int
    device_info: str | None
    ip_address: str | None
    created_at: datetime
    last_seen_at: datetime
    is_current: bool

    model_config = {"from_attributes": True}


LoginResponse.model_rebuild()
