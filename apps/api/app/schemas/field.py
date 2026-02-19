from datetime import date, datetime
from typing import Annotated, Any

from pydantic import BaseModel, Field, StringConstraints

FieldName = Annotated[str, StringConstraints(strip_whitespace=False, min_length=0, max_length=255)]


class FieldCreateRequest(BaseModel):
    farm_id: str
    name: FieldName
    geometry: dict[str, Any]


class FieldUpdateRequest(BaseModel):
    name: FieldName | None = None
    geometry: dict[str, Any] | None = None


class FieldResponse(BaseModel):
    id: str
    farm_id: str
    name: str
    area_ha: float
    geometry: dict[str, Any]
    schedule: dict[str, Any] | None = None


class ImagerySearchResponse(BaseModel):
    scene_id: str
    acquisition_date: datetime
    cloud_cover: float | None = None
    provider: str
    collection: str
    bbox: list[float] | None = None
    footprint_geojson: dict[str, Any] | None = None
    preview_url: str | None = None
    field_coverage_ratio: float | None = None


class FieldScheduleUpdateRequest(BaseModel):
    enabled: bool = True
    timezone: str = "UTC"
    local_time: str = "06:00"
    frequency: str = Field(default="daily", pattern="^(daily|weekly)$")


class AnalysisCreateRequest(BaseModel):
    scene_id: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    max_cloud: float | None = Field(default=20.0, ge=0, le=100)
    include_sr: bool = False
    include_radar_overlay: bool = True


class AnalysisJobResponse(BaseModel):
    id: str
    status: str
    queue: str
    error_message: str | None = None
    result_json: dict[str, Any] | None = None


class TimeSeriesPoint(BaseModel):
    id: str
    observed_on: date
    status: str
    cloud_cover: float | None = None
    valid_pixel_ratio: float | None = None
    indices_native: dict[str, Any]
    indices_sr: dict[str, Any]


class TimeSeriesResponse(BaseModel):
    field_id: str
    points: list[TimeSeriesPoint]


class TimelineClearResponse(BaseModel):
    field_id: str
    deleted_observations: int
    deleted_scene_candidates: int
    deleted_analysis_jobs: int
    deleted_layer_assets: int
    deleted_total: int
