from pydantic import BaseModel

from app.models import ExportFormatEnum


class ExportCreateRequest(BaseModel):
    field_id: str
    format: ExportFormatEnum
    layer_id: str | None = None
    index_name: str | None = None
    source_mode: str | None = None
    observed_on: str | None = None


class ExportJobResponse(BaseModel):
    id: str
    status: str
    format: str
    output_uri: str | None = None
    error_message: str | None = None
