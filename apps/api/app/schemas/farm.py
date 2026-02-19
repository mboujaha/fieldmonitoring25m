from datetime import datetime

from pydantic import BaseModel, Field


class FarmCreateRequest(BaseModel):
    organization_id: str
    name: str = Field(min_length=2, max_length=255)
    description: str | None = None


class FarmResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    description: str | None
    created_at: datetime
