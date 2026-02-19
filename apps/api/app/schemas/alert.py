from datetime import datetime

from pydantic import BaseModel


class AlertResponse(BaseModel):
    id: str
    organization_id: str
    field_id: str | None
    severity: str
    category: str
    message: str
    acknowledged_at: datetime | None
    metadata_json: dict


class AlertsClearResponse(BaseModel):
    deleted_alerts: int
