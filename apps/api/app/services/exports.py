from __future__ import annotations

import csv
import io
from uuid import UUID
from datetime import datetime, timezone

import httpx
import numpy as np
import rasterio
from PIL import Image, ImageDraw
from rasterio.io import MemoryFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AnalysisJob, ExportFormatEnum, ExportJob, Field, JobStatusEnum, LayerAsset, LayerTypeEnum, Observation
from app.services.storage import build_object_key, download_bytes as download_object_storage_bytes, upload_bytes


def _build_csv_export(db: Session, field_id: UUID) -> bytes:
    observations = (
        db.query(Observation)
        .filter(Observation.field_id == field_id)
        .order_by(Observation.observed_on.asc())
        .all()
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["observed_on", "status", "cloud_cover", "valid_pixel_ratio", "ndvi_mean", "ndmi_mean", "ndwi_mean"])
    for obs in observations:
        ndvi = (obs.indices_native.get("NDVI", {}).get("stats") or {}).get("mean")
        ndmi = (obs.indices_native.get("NDMI", {}).get("stats") or {}).get("mean")
        ndwi = (obs.indices_native.get("NDWI", {}).get("stats") or {}).get("mean")
        writer.writerow([obs.observed_on.isoformat(), obs.status.value, obs.cloud_cover, obs.valid_pixel_ratio, ndvi, ndmi, ndwi])
    return buffer.getvalue().encode("utf-8")


def _build_png_export(field_name: str, metrics: dict[str, float | None]) -> bytes:
    width, height = 1100, 700
    img = Image.new("RGB", (width, height), color=(243, 245, 237))
    draw = ImageDraw.Draw(img)

    draw.rectangle((0, 0, width, 90), fill=(34, 74, 44))
    draw.text((30, 30), f"Field Snapshot: {field_name}", fill=(255, 255, 255))

    y = 140
    for key, value in metrics.items():
        draw.text((40, y), f"{key}: {value if value is not None else 'N/A'}", fill=(22, 22, 22))
        y += 52

    timestamp = datetime.now(timezone.utc).isoformat()
    draw.text((40, 640), f"Generated UTC: {timestamp}", fill=(80, 80, 80))

    output = io.BytesIO()
    img.save(output, format="PNG")
    return output.getvalue()


def _download_bytes(url: str) -> bytes:
    try:
        return download_object_storage_bytes(url)
    except Exception:
        response = httpx.get(url, timeout=60.0)
        response.raise_for_status()
        return response.content


def _latest_layer_for_export(
    db: Session,
    field_id: UUID,
    params: dict,
    *,
    prefer_rgb: bool = False,
) -> LayerAsset | None:
    layer_id = params.get("layer_id")
    if layer_id:
        try:
            return db.get(LayerAsset, UUID(layer_id))
        except ValueError:
            return None

    index_name = str(params.get("index_name") or "").upper()
    source_mode = str(params.get("source_mode") or "native").lower()
    expect_model_derived = source_mode == "sr"

    def _pick_from_query(query):
        if prefer_rgb:
            rgb_layer = (
                query.filter(LayerAsset.layer_type == LayerTypeEnum.RGB)
                .order_by(LayerAsset.created_at.desc())
                .first()
            )
            if rgb_layer:
                return rgb_layer

        if index_name:
            index_layer = query.filter(LayerAsset.index_name == index_name).order_by(LayerAsset.created_at.desc()).first()
            if index_layer:
                return index_layer

        return query.order_by(LayerAsset.created_at.desc()).first()

    query = db.query(LayerAsset).filter(
        LayerAsset.field_id == field_id,
        LayerAsset.is_model_derived == expect_model_derived,
    )
    selected = _pick_from_query(query)
    if selected:
        return selected

    # If SR was requested but not available yet, gracefully fall back to native imagery/layers.
    if expect_model_derived:
        fallback_query = db.query(LayerAsset).filter(
            LayerAsset.field_id == field_id,
            LayerAsset.is_model_derived.is_(False),
        )
        fallback = _pick_from_query(fallback_query)
        if fallback:
            return fallback

    return None


def _build_geotiff_export_from_layer(layer: LayerAsset | None) -> bytes:
    if layer is None or not layer.source_uri:
        raise RuntimeError("No layer asset available for GeoTIFF export")
    return _download_bytes(layer.source_uri)


def _stretch_channel(channel: np.ndarray) -> np.ndarray:
    finite = channel[np.isfinite(channel)]
    if finite.size == 0:
        return np.zeros(channel.shape, dtype=np.uint8)

    p2 = float(np.nanpercentile(finite, 2))
    p98 = float(np.nanpercentile(finite, 98))
    denom = (p98 - p2) if p98 > p2 else 1.0
    normalized = np.clip((channel - p2) / denom, 0.0, 1.0)
    return (normalized * 255).astype(np.uint8)


def _build_png_export_from_layer(field_name: str, layer: LayerAsset | None, metrics: dict[str, float | None]) -> bytes:
    if layer is None or not layer.source_uri:
        return _build_png_export(field_name=field_name, metrics=metrics)

    payload = _download_bytes(layer.source_uri)
    with MemoryFile(payload) as memfile:
        with memfile.open() as dataset:
            if dataset.count >= 3:
                stacked = dataset.read([1, 2, 3]).astype(np.float32)
                red = _stretch_channel(stacked[0])
                green = _stretch_channel(stacked[1])
                blue = _stretch_channel(stacked[2])
                rgb = np.stack([red, green, blue], axis=-1)
                rgb[~np.isfinite(stacked).all(axis=0)] = np.array([0, 0, 0], dtype=np.uint8)
                image = Image.fromarray(rgb, mode="RGB")
            else:
                raster = dataset.read(1).astype(np.float32)
                finite = raster[np.isfinite(raster)]
                if finite.size == 0:
                    return _build_png_export(field_name=field_name, metrics=metrics)

                normalized = _stretch_channel(raster).astype(np.float32) / 255.0
                rgb = np.zeros((normalized.shape[0], normalized.shape[1], 3), dtype=np.uint8)
                rgb[..., 0] = (90 + normalized * 60).astype(np.uint8)
                rgb[..., 1] = (70 + normalized * 170).astype(np.uint8)
                rgb[..., 2] = (40 + normalized * 70).astype(np.uint8)
                rgb[~np.isfinite(raster)] = np.array([20, 20, 20], dtype=np.uint8)
                image = Image.fromarray(rgb, mode="RGB")

    max_dim = 1600
    if max(image.size) > max_dim:
        image.thumbnail((max_dim, max_dim), Image.Resampling.BICUBIC)
    elif max(image.size) < 800:
        scale = 800 / float(max(image.size))
        resized = (
            max(1, int(round(image.size[0] * scale))),
            max(1, int(round(image.size[1] * scale))),
        )
        image = image.resize(resized, Image.Resampling.BICUBIC)

    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def run_export_job(db: Session, export_job: ExportJob) -> dict:
    export_job.status = JobStatusEnum.RUNNING
    db.flush()
    settings = get_settings()

    field = db.get(Field, export_job.field_id)
    if field is None:
        raise RuntimeError("Export field not found")

    payload: bytes
    content_type: str
    extension: str
    export_params = export_job.params_json or {}
    requested_source_mode = str(export_params.get("source_mode") or "native").lower()
    selected_layer = _latest_layer_for_export(
        db=db,
        field_id=field.id,
        params=export_params,
        prefer_rgb=export_job.format == ExportFormatEnum.PNG,
    )

    if requested_source_mode == "sr" and (selected_layer is None or not selected_layer.is_model_derived):
        latest_job = (
            db.query(AnalysisJob)
            .filter(AnalysisJob.field_id == field.id)
            .order_by(AnalysisJob.created_at.desc())
            .first()
        )
        details: list[str] = []
        if latest_job is None:
            details.append("no analysis jobs found")
        else:
            details.append(f"last_job={latest_job.id}")
            details.append(f"last_job_status={latest_job.status.value}")
            result = latest_job.result_json if isinstance(latest_job.result_json, dict) else {}
            result_status = result.get("status")
            if isinstance(result_status, str):
                details.append(f"result_status={result_status}")
            reason = result.get("reason")
            if isinstance(reason, str):
                details.append(f"reason={reason}")
            sr_visualization_generated = result.get("sr_visualization_generated")
            if isinstance(sr_visualization_generated, bool):
                details.append(f"sr_visualization_generated={str(sr_visualization_generated).lower()}")
            sr_requested = result.get("sr_requested")
            if isinstance(sr_requested, bool):
                details.append(f"sr_requested={str(sr_requested).lower()}")
            sr_provider = result.get("sr_provider")
            if isinstance(sr_provider, str) and sr_provider:
                details.append(f"sr_provider={sr_provider}")

        if settings.app_env.strip().lower() in {"development", "dev"}:
            details.append("APP_ENV is development; SR4RS jobs may be routed to analysis_cpu instead of sr_gpu")

        detail_text = ", ".join(details) if details else "unknown cause"
        raise RuntimeError(
            "No SR MODEL_DERIVED layer available for export. "
            "Run analysis with SR enabled and a working SR provider, then retry. "
            f"Diagnostics: {detail_text}"
        )

    if export_job.format == ExportFormatEnum.CSV:
        payload = _build_csv_export(db, field.id)
        content_type = "text/csv"
        extension = "csv"
    elif export_job.format == ExportFormatEnum.PNG:
        latest = (
            db.query(Observation)
            .filter(Observation.field_id == field.id)
            .order_by(Observation.observed_on.desc())
            .first()
        )
        latest_metrics = {
            "NDVI mean": ((latest.indices_native.get("NDVI", {}).get("stats") or {}).get("mean") if latest else None),
            "NDMI mean": ((latest.indices_native.get("NDMI", {}).get("stats") or {}).get("mean") if latest else None),
            "NDWI mean": ((latest.indices_native.get("NDWI", {}).get("stats") or {}).get("mean") if latest else None),
        }
        payload = _build_png_export_from_layer(field_name=field.name, layer=selected_layer, metrics=latest_metrics)
        content_type = "image/png"
        extension = "png"
    else:
        payload = _build_geotiff_export_from_layer(selected_layer)
        content_type = "image/tiff"
        extension = "tif"

    key = build_object_key(prefix="exports", object_id=str(export_job.id), extension=extension)
    output_uri = upload_bytes(key=key, payload=payload, content_type=content_type)

    export_job.output_uri = output_uri
    export_job.status = JobStatusEnum.SUCCEEDED
    db.flush()

    return {"id": str(export_job.id), "status": export_job.status.value, "output_uri": output_uri}
