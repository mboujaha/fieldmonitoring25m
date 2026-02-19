from datetime import datetime

from pydantic import BaseModel


class LayerMetadataResponse(BaseModel):
    id: str
    field_id: str
    layer_type: str
    index_name: str | None
    source_uri: str
    tilejson_url: str | None
    is_model_derived: bool
    provenance: str
    resolution_m: float | None = None
    quality_status: str | None = None
    required_bands_met: bool | None = None
    metadata_json: dict
    created_at: datetime
