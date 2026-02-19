import io
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.deps import get_current_user, require_org_role
from app.db.session import get_db
from app.models import Farm, Field, LayerAsset, User
from app.schemas import LayerMetadataResponse
from app.services.storage import create_presigned_get_url

router = APIRouter(prefix="", tags=["layers"])

INDEX_COLORMAPS = {
    "NDVI": "ylgn",
    "NDMI": "ylgnbu",
    "NDWI": "gnbu",
    "EVI": "ylgn",
    "NDRE": "ylorbr",
    "SAVI": "ylgn",
}


@router.get("/layers/{layer_id}/metadata", response_model=LayerMetadataResponse)
def get_layer_metadata(
    layer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LayerMetadataResponse:
    layer = db.get(LayerAsset, layer_id)
    if layer is None:
        raise HTTPException(status_code=404, detail="Layer not found")

    field = db.get(Field, layer.field_id)
    if field is None:
        raise HTTPException(status_code=404, detail="Field not found")

    farm = db.get(Farm, field.farm_id)
    if farm is None:
        raise HTTPException(status_code=404, detail="Farm not found")

    require_org_role(org_id=farm.organization_id, user_id=current_user.id, db=db)

    metadata_json = layer.metadata_json or {}
    provenance = "MODEL_DERIVED" if layer.is_model_derived else "NATIVE"
    quality_status = metadata_json.get("quality_status")
    required_bands_met = metadata_json.get("required_bands_met")
    resolution_m = metadata_json.get("resolution_m")
    if isinstance(resolution_m, str):
        try:
            resolution_m = float(resolution_m)
        except ValueError:
            resolution_m = None

    return LayerMetadataResponse(
        id=str(layer.id),
        field_id=str(layer.field_id),
        layer_type=layer.layer_type.value,
        index_name=layer.index_name,
        source_uri=layer.source_uri,
        tilejson_url=layer.tilejson_url,
        is_model_derived=layer.is_model_derived,
        provenance=provenance,
        resolution_m=resolution_m,
        quality_status=quality_status,
        required_bands_met=required_bands_met,
        metadata_json=metadata_json,
        created_at=layer.created_at,
    )


@router.get("/tiles/{layer_id}/{z}/{x}/{y}.png")
def render_tile(
    layer_id: UUID,
    z: int,
    x: int,
    y: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    settings = get_settings()
    layer = db.get(LayerAsset, layer_id)
    if layer is None:
        raise HTTPException(status_code=404, detail="Layer not found")

    field = db.get(Field, layer.field_id)
    if field is None:
        raise HTTPException(status_code=404, detail="Field not found")

    farm = db.get(Farm, field.farm_id)
    if farm is None:
        raise HTTPException(status_code=404, detail="Farm not found")

    require_org_role(org_id=farm.organization_id, user_id=current_user.id, db=db)

    if not layer.source_uri:
        raise HTTPException(status_code=404, detail="Layer source is missing")

    tiler_url = settings.tiler_internal_url.rstrip("/")
    endpoint = f"{tiler_url}/cog/tiles/WebMercatorQuad/{z}/{x}/{y}.png"
    source_url = create_presigned_get_url(layer.source_uri, expires_seconds=900)
    params: dict[str, str] = {"url": source_url}

    if layer.index_name:
        params["rescale"] = "-1,1"
        colormap = INDEX_COLORMAPS.get(layer.index_name.upper())
        if colormap:
            params["colormap_name"] = colormap

    try:
        response = httpx.get(endpoint, params=params, timeout=45.0)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Tiler unavailable: {exc}") from exc

    if response.status_code == 404 and "outside bounds" in response.text.lower():
        empty = io.BytesIO()
        Image.new("RGBA", (256, 256), (0, 0, 0, 0)).save(empty, format="PNG")
        empty.seek(0)
        return StreamingResponse(empty, media_type="image/png")

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Tiler failed ({response.status_code}): {response.text[:300]}",
        )

    output = io.BytesIO(response.content)
    output.seek(0)
    media_type = response.headers.get("content-type", "image/png")
    return StreamingResponse(output, media_type=media_type)
