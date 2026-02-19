import uuid
import logging
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from shapely.geometry import mapping
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.deps import get_current_user, require_org_role
from app.db.session import get_db
from app.models import (
    AnalysisJob,
    Farm,
    Field,
    FieldRevision,
    JobStatusEnum,
    LayerAsset,
    Membership,
    Observation,
    RoleEnum,
    SceneCandidate,
    User,
)
from app.schemas import (
    AnalysisCreateRequest,
    AnalysisJobResponse,
    FieldCreateRequest,
    FieldResponse,
    FieldScheduleUpdateRequest,
    FieldUpdateRequest,
    ImagerySearchResponse,
    TimelineClearResponse,
    TimeSeriesPoint,
    TimeSeriesResponse,
)
from app.services.analysis import search_field_imagery
from app.services.geometry import (
    GeometryValidationError,
    area_hectares,
    enforce_area_limit,
    multipolygon_to_geojson_dict,
    parse_geojson_geometry,
    parse_uploaded_geometry,
)
from app.services.geometry_db import to_shape_from_wkb, to_wkb_element
from app.services.planetary_computer import scene_field_coverage_ratio, scene_to_geometry
from app.services.queue import celery_client

router = APIRouter(prefix="/fields", tags=["fields"])
logger = logging.getLogger("app.fields")


def _validation_error(field_name: str, message: str, code: str = "value_error") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=[{"loc": ["body", field_name], "msg": message, "type": code}],
    )


def _parse_uuid(value: str, field_name: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        logger.warning("Invalid UUID payload field_name=%s value=%s", field_name, value)
        raise _validation_error(field_name, f"Invalid {field_name}: expected UUID format", code="uuid_invalid") from exc


def _normalize_field_name(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        logger.warning("Invalid field name payload reason=empty_after_trim raw_name=%s", value)
        raise _validation_error("name", "Invalid name: must contain at least 1 non-space character", code="name_empty")
    if len(cleaned) > 255:
        logger.warning("Invalid field name payload reason=too_long name_length=%s", len(cleaned))
        raise _validation_error("name", "Invalid name: exceeds 255 characters", code="name_too_long")
    return cleaned


def _farm_with_role_check(db: Session, farm_id: UUID, user_id: uuid.UUID, minimum: RoleEnum) -> Farm:
    farm = db.get(Farm, farm_id)
    if farm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")
    require_org_role(org_id=farm.organization_id, user_id=user_id, db=db, minimum=minimum)
    return farm


def _field_response(field: Field, geometry_dict: dict | None = None) -> FieldResponse:
    metadata = field.metadata_json or {}
    schedule = metadata.get("schedule")
    if geometry_dict is None:
        geometry_dict = multipolygon_to_geojson_dict(to_shape_from_wkb(field.geometry))
    return FieldResponse(
        id=str(field.id),
        farm_id=str(field.farm_id),
        name=field.name,
        area_ha=field.area_ha,
        geometry=geometry_dict,
        schedule=schedule if isinstance(schedule, dict) else None,
    )


@router.get("", response_model=list[FieldResponse])
def list_fields(
    farm_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[FieldResponse]:
    query = (
        db.query(Field)
        .join(Farm, Field.farm_id == Farm.id)
        .join(Membership, Membership.organization_id == Farm.organization_id)
        .filter(Membership.user_id == current_user.id)
    )
    if farm_id is not None:
        query = query.filter(Field.farm_id == farm_id)

    fields = query.order_by(Field.created_at.desc()).all()
    return [_field_response(field) for field in fields]


@router.post("", response_model=FieldResponse)
def create_field(
    payload: FieldCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FieldResponse:
    farm = _farm_with_role_check(db, _parse_uuid(payload.farm_id, "farm_id"), current_user.id, RoleEnum.ANALYST)
    field_name = _normalize_field_name(payload.name)

    try:
        geometry = parse_geojson_geometry(payload.geometry)
        area_ha = area_hectares(geometry)
        enforce_area_limit(area_ha)
    except GeometryValidationError as exc:
        logger.warning(
            "Field create geometry rejected farm_id=%s name=%s geometry_type=%s reason=%s",
            str(farm.id),
            field_name,
            payload.geometry.get("type"),
            str(exc),
        )
        raise _validation_error("geometry", str(exc), code="geometry_invalid") from exc

    field = Field(
        farm_id=farm.id,
        name=field_name,
        geometry=to_wkb_element(geometry),
        area_ha=area_ha,
        metadata_json={},
    )
    db.add(field)
    db.flush()

    db.add(
        FieldRevision(
            field_id=field.id,
            changed_by_id=current_user.id,
            geometry=to_wkb_element(geometry),
            area_ha=area_ha,
        )
    )
    db.commit()

    return _field_response(field, geometry_dict=multipolygon_to_geojson_dict(geometry))


@router.post("/import", response_model=FieldResponse)
async def import_field(
    farm_id: str = Form(...),
    name: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FieldResponse:
    farm = _farm_with_role_check(db, _parse_uuid(farm_id, "farm_id"), current_user.id, RoleEnum.ANALYST)
    field_name = _normalize_field_name(name)

    content = await file.read()
    try:
        geometry = parse_uploaded_geometry(file.filename or "uploaded.geojson", content)
        area_ha = area_hectares(geometry)
        enforce_area_limit(area_ha)
    except GeometryValidationError as exc:
        logger.warning(
            "Field import geometry rejected farm_id=%s name=%s filename=%s reason=%s",
            str(farm.id),
            field_name,
            file.filename,
            str(exc),
        )
        raise _validation_error("geometry", str(exc), code="geometry_invalid") from exc

    field = Field(
        farm_id=farm.id,
        name=field_name,
        geometry=to_wkb_element(geometry),
        area_ha=area_ha,
        metadata_json={"source_upload": file.filename},
    )
    db.add(field)
    db.flush()

    db.add(
        FieldRevision(
            field_id=field.id,
            changed_by_id=current_user.id,
            geometry=to_wkb_element(geometry),
            area_ha=area_ha,
        )
    )
    db.commit()

    return _field_response(field, geometry_dict=multipolygon_to_geojson_dict(geometry))


@router.patch("/{field_id}", response_model=FieldResponse)
def update_field(
    field_id: UUID,
    payload: FieldUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FieldResponse:
    field = db.get(Field, field_id)
    if field is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")

    farm = _farm_with_role_check(db, field.farm_id, current_user.id, RoleEnum.ANALYST)
    _ = farm

    geometry = to_shape_from_wkb(field.geometry)
    if payload.geometry is not None:
        try:
            geometry = parse_geojson_geometry(payload.geometry)
            area_ha = area_hectares(geometry)
            enforce_area_limit(area_ha)
        except GeometryValidationError as exc:
            logger.warning(
                "Field update geometry rejected field_id=%s name=%s geometry_type=%s reason=%s",
                str(field.id),
                field.name,
                payload.geometry.get("type"),
                str(exc),
            )
            raise _validation_error("geometry", str(exc), code="geometry_invalid") from exc
        field.geometry = to_wkb_element(geometry)
        field.area_ha = area_ha
        db.add(
            FieldRevision(
                field_id=field.id,
                changed_by_id=current_user.id,
                geometry=to_wkb_element(geometry),
                area_ha=area_ha,
            )
        )

    if payload.name:
        field.name = _normalize_field_name(payload.name)

    db.commit()

    return _field_response(field, geometry_dict=multipolygon_to_geojson_dict(geometry))


@router.get("/{field_id}/imagery/search", response_model=list[ImagerySearchResponse])
def search_imagery(
    field_id: UUID,
    date_from: date | None = None,
    date_to: date | None = None,
    max_cloud: float = 20.0,
    collection: str = "sentinel-2-l2a",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ImagerySearchResponse]:
    field = db.get(Field, field_id)
    if field is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")

    farm = db.get(Farm, field.farm_id)
    if farm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")

    require_org_role(org_id=farm.organization_id, user_id=current_user.id, db=db, minimum=RoleEnum.VIEWER)

    if date_from is None or date_to is None:
        today = datetime.now(timezone.utc).date()
        date_from = date_from or (today - timedelta(days=30))
        date_to = date_to or today

    scenes = search_field_imagery(
        db=db,
        field=field,
        date_from=date_from,
        date_to=date_to,
        max_cloud=max_cloud,
        collection=collection,
    )
    settings = get_settings()
    field_geometry = to_shape_from_wkb(field.geometry)
    accepted_scenes: list[ImagerySearchResponse] = []

    for scene in scenes:
        coverage_ratio = scene_field_coverage_ratio(scene=scene, field_geometry=field_geometry)
        if coverage_ratio < settings.min_scene_coverage_ratio:
            continue

        scene_geometry = scene_to_geometry(scene)
        footprint_geojson = mapping(scene_geometry) if scene_geometry is not None else None
        accepted_scenes.append(
            ImagerySearchResponse(
                scene_id=scene.scene_id,
                acquisition_date=scene.acquisition_date,
                cloud_cover=scene.cloud_cover,
                provider="planetary_computer",
                collection=scene.collection,
                bbox=scene.bbox,
                footprint_geojson=footprint_geojson,
                preview_url=scene.preview_url,
                field_coverage_ratio=round(coverage_ratio, 4),
            )
        )

    return accepted_scenes


@router.patch("/{field_id}/schedule", response_model=FieldResponse)
def update_field_schedule(
    field_id: UUID,
    payload: FieldScheduleUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FieldResponse:
    field = db.get(Field, field_id)
    if field is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")

    farm = _farm_with_role_check(db, field.farm_id, current_user.id, RoleEnum.ANALYST)
    _ = farm

    metadata = dict(field.metadata_json or {})
    metadata["schedule"] = {
        "enabled": payload.enabled,
        "timezone": payload.timezone,
        "local_time": payload.local_time,
        "frequency": payload.frequency,
    }
    field.metadata_json = metadata
    db.commit()
    return _field_response(field)


@router.post("/{field_id}/analyses", response_model=AnalysisJobResponse)
def create_analysis(
    field_id: UUID,
    payload: AnalysisCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnalysisJobResponse:
    field = db.get(Field, field_id)
    if field is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")

    farm = db.get(Farm, field.farm_id)
    if farm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")

    require_org_role(org_id=farm.organization_id, user_id=current_user.id, db=db, minimum=RoleEnum.ANALYST)

    settings = get_settings()
    queue_name = "analysis_cpu"
    if (
        payload.include_sr
        and settings.sr_provider.strip().lower() in {"sr4rs", "sr4rs_local"}
        and settings.app_env.strip().lower() not in {"development", "dev"}
    ):
        queue_name = "sr_gpu"

    job = AnalysisJob(
        field_id=field.id,
        requested_by_id=current_user.id,
        status=JobStatusEnum.QUEUED,
        queue=queue_name,
        params_json={
            "scene_id": payload.scene_id,
            "date_from": payload.date_from.isoformat() if payload.date_from else None,
            "date_to": payload.date_to.isoformat() if payload.date_to else None,
            "max_cloud": payload.max_cloud,
            "include_sr": payload.include_sr,
            "include_radar_overlay": payload.include_radar_overlay,
        },
        result_json={},
    )
    db.add(job)
    db.commit()

    celery_client.send_task("worker.tasks.run_analysis_task", args=[str(job.id)], queue=queue_name)

    return AnalysisJobResponse(id=str(job.id), status=job.status.value, queue=job.queue)


@router.get("/{field_id}/analyses/{job_id}", response_model=AnalysisJobResponse)
def get_analysis_job(
    field_id: UUID,
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnalysisJobResponse:
    field = db.get(Field, field_id)
    if field is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")

    farm = db.get(Farm, field.farm_id)
    if farm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")

    require_org_role(org_id=farm.organization_id, user_id=current_user.id, db=db, minimum=RoleEnum.VIEWER)

    job = db.get(AnalysisJob, job_id)
    if job is None or job.field_id != field.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis job not found")

    return AnalysisJobResponse(
        id=str(job.id),
        status=job.status.value,
        queue=job.queue,
        error_message=job.error_message,
        result_json=job.result_json if isinstance(job.result_json, dict) else None,
    )


@router.get("/{field_id}/timeseries", response_model=TimeSeriesResponse)
def get_timeseries(
    field_id: UUID,
    index: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TimeSeriesResponse:
    field = db.get(Field, field_id)
    if field is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")

    farm = db.get(Farm, field.farm_id)
    if farm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")

    require_org_role(org_id=farm.organization_id, user_id=current_user.id, db=db, minimum=RoleEnum.VIEWER)

    observations = (
        db.query(Observation)
        .filter(Observation.field_id == field.id)
        .order_by(Observation.observed_on.asc())
        .all()
    )
    points: list[TimeSeriesPoint] = []
    for obs in observations:
        native = obs.indices_native
        sr = obs.indices_sr
        if index:
            native = {index: native.get(index)} if native.get(index) else {}
            sr = {index: sr.get(index)} if sr.get(index) else {}
        points.append(
            TimeSeriesPoint(
                id=str(obs.id),
                observed_on=obs.observed_on,
                status=obs.status.value,
                cloud_cover=obs.cloud_cover,
                valid_pixel_ratio=obs.valid_pixel_ratio,
                indices_native=native,
                indices_sr=sr,
            )
        )
    return TimeSeriesResponse(field_id=str(field.id), points=points)


@router.delete("/{field_id}/timeseries", response_model=TimelineClearResponse)
def clear_timeseries(
    field_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TimelineClearResponse:
    field = db.get(Field, field_id)
    if field is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")

    farm = db.get(Farm, field.farm_id)
    if farm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")

    require_org_role(org_id=farm.organization_id, user_id=current_user.id, db=db, minimum=RoleEnum.ANALYST)

    deleted_layer_assets = db.query(LayerAsset).filter(LayerAsset.field_id == field.id).delete(synchronize_session=False)
    deleted_observations = db.query(Observation).filter(Observation.field_id == field.id).delete(synchronize_session=False)
    deleted_analysis_jobs = db.query(AnalysisJob).filter(AnalysisJob.field_id == field.id).delete(synchronize_session=False)
    deleted_scene_candidates = db.query(SceneCandidate).filter(SceneCandidate.field_id == field.id).delete(
        synchronize_session=False
    )
    db.commit()

    deleted_total = deleted_observations + deleted_scene_candidates + deleted_analysis_jobs + deleted_layer_assets
    return TimelineClearResponse(
        field_id=str(field.id),
        deleted_observations=deleted_observations,
        deleted_scene_candidates=deleted_scene_candidates,
        deleted_analysis_jobs=deleted_analysis_jobs,
        deleted_layer_assets=deleted_layer_assets,
        deleted_total=deleted_total,
    )
