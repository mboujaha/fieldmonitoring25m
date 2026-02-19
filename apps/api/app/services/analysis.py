from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

import numpy as np
from affine import Affine
from rasterio.io import MemoryFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    AlertSeverityEnum,
    AnalysisJob,
    Farm,
    Field,
    JobStatusEnum,
    LayerAsset,
    LayerTypeEnum,
    Observation,
    ObservationStatusEnum,
    SRModelProfile,
    SceneCandidate,
)
from app.services.alerts import create_alert, maybe_create_ndvi_drop_alert
from app.services.feature_flags import is_enabled
from app.services.geometry_db import to_shape_from_wkb
from app.services.indices import available_indices_for_bands, compute_index_rasters, compute_indices, compute_valid_pixel_ratio
from app.services.planetary_computer import PlanetaryComputerProvider, SceneResult, scene_field_coverage_ratio
from app.services.raster_processing import RasterProcessingError, read_scene_patch
from app.services.storage import build_object_key, upload_bytes
from app.services.sr_engine import SRInferenceError, SRRequest, build_sr_engine


def _default_dates() -> tuple[date, date]:
    today = datetime.now(timezone.utc).date()
    return today - timedelta(days=30), today


def search_field_imagery(
    db: Session,
    field: Field,
    date_from: date | None,
    date_to: date | None,
    max_cloud: float,
    collection: str = "sentinel-2-l2a",
) -> list[SceneResult]:
    provider = PlanetaryComputerProvider()
    geometry = to_shape_from_wkb(field.geometry)
    default_start, default_end = _default_dates()
    start = date_from or default_start
    end = date_to or default_end
    if collection == "sentinel-1-rtc":
        return provider.search_sentinel1_rtc(geometry=geometry, date_from=start, date_to=end)
    return provider.search_sentinel2(geometry=geometry, date_from=start, date_to=end, max_cloud=max_cloud)


def _ensure_sr_model(
    db: Session,
    model_name: str,
    model_version: str,
    supported_bands: list[str],
    scale_factor: float,
    runtime_class: str,
) -> SRModelProfile:
    profile = (
        db.query(SRModelProfile)
        .filter(SRModelProfile.name == model_name, SRModelProfile.version == model_version)
        .one_or_none()
    )
    if profile:
        return profile

    profile = SRModelProfile(
        name=model_name,
        version=model_version,
        supported_bands=supported_bands,
        scale_factor=scale_factor,
        runtime_class=runtime_class,
    )
    db.add(profile)
    db.flush()
    return profile


def _build_scaled_mask(base_mask: np.ndarray, target_shape: tuple[int, int]) -> np.ndarray:
    height, width = target_shape
    if base_mask.shape == target_shape:
        return base_mask

    scale_y = max(int(np.ceil(height / base_mask.shape[0])), 1)
    scale_x = max(int(np.ceil(width / base_mask.shape[1])), 1)
    expanded = base_mask.repeat(scale_y, axis=0).repeat(scale_x, axis=1)
    return expanded[:height, :width]


def _encode_geotiff(values: np.ndarray, transform: Any, crs: str) -> bytes:
    encoded = np.nan_to_num(values.astype(np.float32), nan=-9999.0)
    if encoded.ndim == 2:
        encoded = encoded[np.newaxis, ...]
    if encoded.ndim != 3:
        raise RuntimeError(f"Unexpected raster shape for GeoTIFF encoding: {encoded.shape}")

    count, height, width = encoded.shape
    with MemoryFile() as memfile:
        with memfile.open(
            driver="GTiff",
            height=height,
            width=width,
            count=count,
            dtype=encoded.dtype,
            crs=crs,
            transform=transform,
            nodata=-9999.0,
            tiled=True,
            compress="deflate",
            predictor=2,
        ) as dataset:
            for band_index in range(count):
                dataset.write(encoded[band_index], band_index + 1)
        return memfile.read()


def _derive_resampled_transform(
    transform: Any,
    source_shape: tuple[int, int],
    target_shape: tuple[int, int],
) -> Any:
    if source_shape == target_shape:
        return transform

    src_height, src_width = source_shape
    dst_height, dst_width = target_shape
    if dst_height <= 0 or dst_width <= 0:
        return transform

    scale_x = src_width / float(dst_width)
    scale_y = src_height / float(dst_height)
    return transform * Affine.scale(scale_x, scale_y)


def _create_layer_asset(
    db: Session,
    *,
    field_id: uuid.UUID,
    observation_id: uuid.UUID,
    layer_type: LayerTypeEnum,
    index_name: str,
    values: np.ndarray,
    transform: Any,
    crs: str,
    scene_id: str,
    is_model_derived: bool,
    label: str,
) -> LayerAsset:
    payload = _encode_geotiff(values=values, transform=transform, crs=crs)
    source_family = "sr" if is_model_derived else "native"
    key = build_object_key(
        prefix=f"layers/{field_id}/{observation_id}/{source_family}",
        object_id=f"{index_name.lower()}-{uuid.uuid4()}",
        extension="tif",
    )
    source_uri = upload_bytes(key=key, payload=payload, content_type="image/tiff")
    layer = LayerAsset(
        field_id=field_id,
        observation_id=observation_id,
        layer_type=layer_type,
        index_name=index_name,
        source_uri=source_uri,
        tilejson_url=None,
        is_model_derived=is_model_derived,
        metadata_json={
            "scene_id": scene_id,
            "index": index_name,
            "label": label,
            "provenance": "MODEL_DERIVED" if is_model_derived else "NATIVE",
            "resolution_m": 2.5 if is_model_derived else 10.0,
            "required_bands_met": True,
            "quality_status": "OK",
        },
    )
    db.add(layer)
    db.flush()
    layer.tilejson_url = f"/api/v1/tiles/{layer.id}"  # tile route expands z/x/y
    db.flush()
    return layer


def _create_rgb_layer_asset(
    db: Session,
    *,
    field_id: uuid.UUID,
    observation_id: uuid.UUID,
    red: np.ndarray,
    green: np.ndarray,
    blue: np.ndarray,
    transform: Any,
    crs: str,
    scene_id: str,
    is_model_derived: bool,
    resolution_m: float,
    label: str,
) -> LayerAsset:
    payload = _encode_geotiff(values=np.stack([red, green, blue]), transform=transform, crs=crs)
    source_family = "sr" if is_model_derived else "native"
    key = build_object_key(
        prefix=f"layers/{field_id}/{observation_id}/{source_family}",
        object_id=f"rgb-{uuid.uuid4()}",
        extension="tif",
    )
    source_uri = upload_bytes(key=key, payload=payload, content_type="image/tiff")
    layer = LayerAsset(
        field_id=field_id,
        observation_id=observation_id,
        layer_type=LayerTypeEnum.RGB,
        index_name=None,
        source_uri=source_uri,
        tilejson_url=None,
        is_model_derived=is_model_derived,
        metadata_json={
            "scene_id": scene_id,
            "label": label,
            "visualization": "TRUE_COLOR",
            "provenance": "MODEL_DERIVED" if is_model_derived else "NATIVE",
            "resolution_m": resolution_m,
            "required_bands_met": True,
            "quality_status": "OK",
        },
    )
    db.add(layer)
    db.flush()
    layer.tilejson_url = f"/api/v1/tiles/{layer.id}"
    db.flush()
    return layer


def run_analysis_job(db: Session, job: AnalysisJob) -> dict[str, Any]:
    settings = get_settings()
    job.status = JobStatusEnum.RUNNING
    db.flush()

    field = db.get(Field, job.field_id)
    if field is None:
        raise RuntimeError("Field not found for analysis job")

    farm = db.get(Farm, field.farm_id)
    if farm is None:
        raise RuntimeError("Farm not found for analysis job")
    field_geometry = to_shape_from_wkb(field.geometry)

    params = job.params_json or {}
    max_cloud = float(params.get("max_cloud") or settings.cloud_cap_percent)
    include_sr = bool(params.get("include_sr", False))
    include_radar_overlay = bool(params.get("include_radar_overlay", True))
    requested_scene_id = str(params.get("scene_id") or "").strip()

    date_from = date.fromisoformat(params["date_from"]) if params.get("date_from") else None
    date_to = date.fromisoformat(params["date_to"]) if params.get("date_to") else None

    scenes = search_field_imagery(
        db=db,
        field=field,
        date_from=date_from,
        date_to=date_to,
        max_cloud=max_cloud,
        collection="sentinel-2-l2a",
    )
    selected_scene: SceneResult | None = None
    selected_scene_coverage = 0.0
    if requested_scene_id:
        selected_scene = next((scene for scene in scenes if scene.scene_id == requested_scene_id), None)
        if selected_scene is None:
            provider = PlanetaryComputerProvider()
            selected_scene = provider.get_scene_by_id(scene_id=requested_scene_id, collection="sentinel-2-l2a")
            if selected_scene is None:
                job.status = JobStatusEnum.FAILED
                job.error_message = f"Requested scene '{requested_scene_id}' was not found."
                job.result_json = {
                    "status": "FAILED",
                    "reason": "REQUESTED_SCENE_NOT_FOUND",
                    "scene_id": requested_scene_id,
                }
                db.flush()
                return job.result_json
        selected_scene_coverage = scene_field_coverage_ratio(scene=selected_scene, field_geometry=field_geometry)

    if selected_scene is None and not scenes:
        job.status = JobStatusEnum.SKIPPED
        job.result_json = {"reason": "No scene available"}
        db.flush()
        return job.result_json

    if selected_scene is None:
        for candidate in scenes:
            coverage = scene_field_coverage_ratio(scene=candidate, field_geometry=field_geometry)
            if coverage >= settings.min_scene_coverage_ratio:
                selected_scene = candidate
                selected_scene_coverage = coverage
                break

        if selected_scene is None:
            job.status = JobStatusEnum.SKIPPED
            job.result_json = {
                "status": "SKIPPED",
                "reason": "NO_SCENE_MEETS_COVERAGE",
                "scene_count": len(scenes),
                "min_scene_coverage_ratio": settings.min_scene_coverage_ratio,
            }
            db.flush()
            return job.result_json

    scene_candidate = SceneCandidate(
        field_id=field.id,
        provider="planetary_computer",
        collection=selected_scene.collection,
        scene_id=selected_scene.scene_id,
        acquisition_date=selected_scene.acquisition_date,
        cloud_cover=selected_scene.cloud_cover,
        assets_json=selected_scene.assets,
    )
    db.add(scene_candidate)
    db.flush()

    if selected_scene_coverage < settings.min_scene_coverage_ratio:
        observation = Observation(
            field_id=field.id,
            scene_candidate_id=scene_candidate.id,
            observed_on=selected_scene.acquisition_date.date(),
            status=ObservationStatusEnum.LOW_QUALITY_SKIPPED,
            cloud_cover=selected_scene.cloud_cover,
            valid_pixel_ratio=selected_scene_coverage,
            indices_native={},
            indices_sr={},
        )
        db.add(observation)
        create_alert(
            db=db,
            organization_id=str(farm.organization_id),
            field_id=str(field.id),
            severity=AlertSeverityEnum.WARN,
            category="LOW_SCENE_COVERAGE",
            message=(
                "Scene skipped: "
                f"field_coverage={selected_scene_coverage:.3f} "
                f"(min={settings.min_scene_coverage_ratio:.3f})."
            ),
            metadata_json={
                "scene_id": selected_scene.scene_id,
                "field_coverage_ratio": selected_scene_coverage,
                "min_scene_coverage_ratio": settings.min_scene_coverage_ratio,
            },
        )
        job.status = JobStatusEnum.SKIPPED
        job.result_json = {
            "status": "SKIPPED",
            "reason": "LOW_SCENE_COVERAGE",
            "scene_id": selected_scene.scene_id,
            "field_coverage_ratio": selected_scene_coverage,
            "min_scene_coverage_ratio": settings.min_scene_coverage_ratio,
        }
        db.flush()
        return job.result_json

    try:
        bands, valid_mask, native_transform, native_crs = read_scene_patch(
            assets=selected_scene.assets,
            aoi_geometry=field_geometry,
            bands=["B02", "B03", "B04", "B05", "B08", "B11"],
        )
    except RasterProcessingError as exc:
        observation = Observation(
            field_id=field.id,
            scene_candidate_id=scene_candidate.id,
            observed_on=selected_scene.acquisition_date.date(),
            status=ObservationStatusEnum.FAILED,
            cloud_cover=selected_scene.cloud_cover,
            valid_pixel_ratio=0.0,
            indices_native={},
            indices_sr={},
        )
        db.add(observation)
        job.status = JobStatusEnum.FAILED
        job.error_message = str(exc)
        db.flush()
        raise

    valid_pixel_ratio = compute_valid_pixel_ratio(valid_mask)
    scene_candidate.valid_pixel_ratio = valid_pixel_ratio

    cloud_cover = selected_scene.cloud_cover if selected_scene.cloud_cover is not None else 0.0
    below_quality = cloud_cover > settings.cloud_cap_percent or valid_pixel_ratio < settings.min_valid_pixel_ratio

    if below_quality:
        observation = Observation(
            field_id=field.id,
            scene_candidate_id=scene_candidate.id,
            observed_on=selected_scene.acquisition_date.date(),
            status=ObservationStatusEnum.LOW_QUALITY_SKIPPED,
            cloud_cover=selected_scene.cloud_cover,
            valid_pixel_ratio=valid_pixel_ratio,
            indices_native={},
            indices_sr={},
        )
        db.add(observation)
        create_alert(
            db=db,
            organization_id=str(farm.organization_id),
            field_id=str(field.id),
            severity=AlertSeverityEnum.WARN,
            category="LOW_QUALITY_SKIPPED",
            message=(
                "Scene skipped: "
                f"cloud={cloud_cover:.2f}% (max={settings.cloud_cap_percent:.2f}%), "
                f"valid_pixels={valid_pixel_ratio:.3f} (min={settings.min_valid_pixel_ratio:.3f})."
            ),
            metadata_json={
                "cloud_cover": cloud_cover,
                "cloud_cap_percent": settings.cloud_cap_percent,
                "valid_pixel_ratio": valid_pixel_ratio,
                "min_valid_pixel_ratio": settings.min_valid_pixel_ratio,
            },
        )
        job.status = JobStatusEnum.SKIPPED
        job.result_json = {
            "status": "LOW_QUALITY_SKIPPED",
            "cloud_cover": cloud_cover,
            "valid_pixel_ratio": valid_pixel_ratio,
            "scene_id": selected_scene.scene_id,
        }
        db.flush()
        return job.result_json

    native_indices = compute_indices(bands=bands, valid_mask=valid_mask)
    native_index_rasters = compute_index_rasters(bands=bands, valid_mask=valid_mask)

    sr_indices: dict[str, Any] = {}
    sr_index_rasters: dict[str, np.ndarray] = {}
    sr_bands: dict[str, np.ndarray] = {}
    sr_model_profile_id = None
    sr_provider = settings.sr_provider
    sr_requested = include_sr
    sr_analytics_enabled = include_sr and is_enabled(db, str(farm.organization_id), "sr_analytics_enabled")
    sr_transform = native_transform
    sr_resolution_m = 2.5

    if sr_requested:
        try:
            sr_engine = build_sr_engine()
            sr_capabilities = sr_engine.get_capabilities()
            if sr_capabilities.scale_factor > 0:
                sr_resolution_m = 10.0 / float(sr_capabilities.scale_factor)
            sr_model = _ensure_sr_model(
                db=db,
                model_name=sr_capabilities.model_name,
                model_version=sr_capabilities.model_version,
                supported_bands=sorted(sr_capabilities.supported_bands),
                scale_factor=float(sr_capabilities.scale_factor),
                runtime_class=sr_capabilities.runtime_class,
            )
            sr_model_profile_id = sr_model.id

            sr_bands = sr_engine.generate(
                SRRequest(
                    acquisition_date=selected_scene.acquisition_date.date(),
                    aoi_geometry=to_shape_from_wkb(field.geometry),
                    native_bands=bands,
                    source_assets=selected_scene.assets,
                )
            )
            if sr_bands and sr_analytics_enabled:
                first_band_shape = next(iter(sr_bands.values())).shape
                sr_transform = _derive_resampled_transform(
                    transform=native_transform,
                    source_shape=valid_mask.shape,
                    target_shape=first_band_shape,
                )
                sr_mask = _build_scaled_mask(base_mask=valid_mask, target_shape=first_band_shape)
                available_indices = available_indices_for_bands(set(sr_bands.keys()))
                computed_sr = compute_indices(bands=sr_bands, valid_mask=sr_mask)
                computed_sr_rasters = compute_index_rasters(bands=sr_bands, valid_mask=sr_mask)
                sr_indices = {k: v for k, v in computed_sr.items() if k in available_indices}
                sr_index_rasters = {k: v for k, v in computed_sr_rasters.items() if k in available_indices}
            elif sr_bands:
                first_band_shape = next(iter(sr_bands.values())).shape
                sr_transform = _derive_resampled_transform(
                    transform=native_transform,
                    source_shape=valid_mask.shape,
                    target_shape=first_band_shape,
                )
        except SRInferenceError as exc:
            create_alert(
                db=db,
                organization_id=str(farm.organization_id),
                field_id=str(field.id),
                severity=AlertSeverityEnum.WARN,
                category="SR_INFERENCE_FAILED",
                message="SR inference failed; native analytics were kept.",
                metadata_json={"provider": sr_provider, "error": str(exc)},
            )

    observation = Observation(
        field_id=field.id,
        scene_candidate_id=scene_candidate.id,
        observed_on=selected_scene.acquisition_date.date(),
        status=ObservationStatusEnum.SUCCEEDED,
        cloud_cover=selected_scene.cloud_cover,
        valid_pixel_ratio=valid_pixel_ratio,
        indices_native=native_indices,
        indices_sr=sr_indices,
        sr_model_profile_id=sr_model_profile_id,
    )
    db.add(observation)
    db.flush()

    for index_name, values in native_index_rasters.items():
        _create_layer_asset(
            db=db,
            field_id=field.id,
            observation_id=observation.id,
            layer_type=LayerTypeEnum.NATIVE_INDEX,
            index_name=index_name,
            values=values,
            transform=native_transform,
            crs=native_crs,
            scene_id=selected_scene.scene_id,
            is_model_derived=False,
            label="NATIVE",
        )

    if {"B04", "B03", "B02"}.issubset(bands.keys()):
        _create_rgb_layer_asset(
            db=db,
            field_id=field.id,
            observation_id=observation.id,
            red=bands["B04"],
            green=bands["B03"],
            blue=bands["B02"],
            transform=native_transform,
            crs=native_crs,
            scene_id=selected_scene.scene_id,
            is_model_derived=False,
            resolution_m=10.0,
            label="NATIVE",
        )

    for index_name, values in sr_index_rasters.items():
        _create_layer_asset(
            db=db,
            field_id=field.id,
            observation_id=observation.id,
            layer_type=LayerTypeEnum.SR_INDEX,
            index_name=index_name,
            values=values,
            transform=sr_transform,
            crs=native_crs,
            scene_id=selected_scene.scene_id,
            is_model_derived=True,
            label="MODEL_DERIVED",
        )

    if {"B04", "B03", "B02"}.issubset(sr_bands.keys()):
        _create_rgb_layer_asset(
            db=db,
            field_id=field.id,
            observation_id=observation.id,
            red=sr_bands["B04"],
            green=sr_bands["B03"],
            blue=sr_bands["B02"],
            transform=sr_transform,
            crs=native_crs,
            scene_id=selected_scene.scene_id,
            is_model_derived=True,
            resolution_m=sr_resolution_m,
            label="MODEL_DERIVED",
        )

    if include_radar_overlay:
        center_date = selected_scene.acquisition_date.date()
        radar_scenes = search_field_imagery(
            db=db,
            field=field,
            date_from=center_date - timedelta(days=3),
            date_to=center_date + timedelta(days=3),
            max_cloud=100.0,
            collection="sentinel-1-rtc",
        )
        if radar_scenes:
            radar_scene = radar_scenes[0]
            radar_source = radar_scene.assets.get("visual") or radar_scene.assets.get("vv") or next(
                iter(radar_scene.assets.values()),
                "",
            )
            db.add(
                LayerAsset(
                    field_id=field.id,
                    observation_id=observation.id,
                    layer_type=LayerTypeEnum.RADAR,
                    index_name=None,
                    source_uri=radar_source,
                    tilejson_url=None,
                    is_model_derived=False,
                    metadata_json={
                        "scene_id": radar_scene.scene_id,
                        "collection": radar_scene.collection,
                        "overlay_type": "SENTINEL1_RTC",
                    },
                )
            )

    maybe_create_ndvi_drop_alert(db=db, organization_id=str(farm.organization_id), field=field, current_observation=observation)

    job.status = JobStatusEnum.SUCCEEDED
    job.result_json = {
        "scene_id": selected_scene.scene_id,
        "cloud_cover": selected_scene.cloud_cover,
        "valid_pixel_ratio": valid_pixel_ratio,
        "native_indices": list(native_indices.keys()),
        "sr_indices": list(sr_indices.keys()),
        "sr_provider": sr_provider if sr_requested else None,
        "sr_requested": sr_requested,
        "sr_analytics_enabled": sr_analytics_enabled,
        "sr_visualization_generated": bool(sr_bands),
    }
    db.flush()
    return job.result_json
