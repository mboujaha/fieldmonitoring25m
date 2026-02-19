import json
import tempfile
from pathlib import Path
from typing import Any

import pyogrio
from pyproj import Geod
from shapely import geometry
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

MAX_FIELD_AREA_HA = 10_000.0
geod = Geod(ellps="WGS84")


class GeometryValidationError(ValueError):
    pass


def _as_multipolygon(shape: geometry.base.BaseGeometry) -> MultiPolygon:
    if isinstance(shape, Polygon):
        return MultiPolygon([shape])
    if isinstance(shape, MultiPolygon):
        return shape
    if shape.geom_type == "GeometryCollection":
        polys = [g for g in shape.geoms if isinstance(g, (Polygon, MultiPolygon))]
        if not polys:
            raise GeometryValidationError("Geometry must include at least one polygon")
        merged = unary_union(polys)
        if isinstance(merged, Polygon):
            return MultiPolygon([merged])
        if isinstance(merged, MultiPolygon):
            return merged
    raise GeometryValidationError("Only Polygon/MultiPolygon geometries are supported")


def _fix_geometry(shape: geometry.base.BaseGeometry) -> geometry.base.BaseGeometry:
    if not shape.is_valid:
        shape = shape.buffer(0)
    if shape.is_empty:
        raise GeometryValidationError("Geometry is empty after validation")
    return shape


def parse_geojson_geometry(raw_geometry: dict[str, Any]) -> MultiPolygon:
    try:
        shape = geometry.shape(raw_geometry)
    except Exception as exc:
        raise GeometryValidationError("Invalid GeoJSON geometry") from exc

    shape = _fix_geometry(shape)
    multi = _as_multipolygon(shape)
    return multi


def parse_uploaded_geometry(filename: str, payload: bytes) -> MultiPolygon:
    suffix = Path(filename).suffix.lower()
    if suffix in {".json", ".geojson"}:
        parsed = json.loads(payload.decode("utf-8"))
        if parsed.get("type") == "FeatureCollection":
            geoms = [geometry.shape(feature["geometry"]) for feature in parsed.get("features", [])]
            merged = unary_union(geoms) if geoms else None
            if merged is None:
                raise GeometryValidationError("FeatureCollection is empty")
            return _as_multipolygon(_fix_geometry(merged))
        if parsed.get("type") == "Feature":
            return parse_geojson_geometry(parsed["geometry"])
        return parse_geojson_geometry(parsed)

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / filename
        file_path.write_bytes(payload)
        read_path = file_path
        if suffix == ".zip":
            read_path = Path(f"/vsizip/{file_path}")
        try:
            frame = pyogrio.read_dataframe(read_path)
        except Exception as exc:
            raise GeometryValidationError("Unsupported or invalid GIS file") from exc
        if frame.empty:
            raise GeometryValidationError("Uploaded file does not contain geometry")
        merged = unary_union(frame.geometry.tolist())
        return _as_multipolygon(_fix_geometry(merged))


def area_hectares(multi_polygon: MultiPolygon) -> float:
    area_m2, _ = geod.geometry_area_perimeter(multi_polygon)
    return abs(area_m2) / 10_000.0


def enforce_area_limit(area_ha: float, limit_ha: float = MAX_FIELD_AREA_HA) -> None:
    if area_ha > limit_ha:
        raise GeometryValidationError(f"Field area {area_ha:.2f} ha exceeds {limit_ha:.0f} ha limit")


def multipolygon_to_geojson_dict(multi_polygon: MultiPolygon) -> dict[str, Any]:
    return geometry.mapping(multi_polygon)
