from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models import RoleEnum


class OrganizationCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)


class OrganizationResponse(BaseModel):
    id: str
    name: str
    created_at: datetime


class InviteCreateRequest(BaseModel):
    email: EmailStr
    role: RoleEnum


class InviteResponse(BaseModel):
    id: str
    email: EmailStr
    role: RoleEnum
    status: str
    expires_at: datetime
