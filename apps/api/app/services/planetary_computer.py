from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import planetary_computer
import pystac_client
from shapely.geometry import Polygon, mapping, shape as shapely_shape
from shapely.geometry.base import BaseGeometry

from app.core.config import get_settings


@dataclass
class SceneResult:
    scene_id: str
    collection: str
    acquisition_date: datetime
    cloud_cover: float | None
    assets: dict[str, str]
    bbox: list[float] | None = None
    footprint_geojson: dict[str, Any] | None = None
    preview_url: str | None = None


def bbox_to_geometry(bbox: list[float] | None) -> BaseGeometry | None:
    if not bbox or len(bbox) != 4:
        return None

    minx, miny, maxx, maxy = bbox
    if minx >= maxx or miny >= maxy:
        return None

    return Polygon([[minx, miny], [maxx, miny], [maxx, maxy], [minx, maxy], [minx, miny]])


def scene_to_geometry(scene: SceneResult) -> BaseGeometry | None:
    if isinstance(scene.footprint_geojson, dict):
        try:
            footprint = shapely_shape(scene.footprint_geojson)
            if not footprint.is_empty:
                return footprint
        except Exception:
            pass
    return bbox_to_geometry(scene.bbox)


def scene_field_coverage_ratio(scene: SceneResult, field_geometry: BaseGeometry) -> float:
    if field_geometry.is_empty or field_geometry.area <= 0:
        return 0.0

    scene_geometry = scene_to_geometry(scene)
    if scene_geometry is None or scene_geometry.is_empty:
        return 0.0

    try:
        covered = scene_geometry.intersection(field_geometry)
    except Exception:
        return 0.0

    if covered.is_empty:
        return 0.0

    return max(0.0, min(1.0, covered.area / field_geometry.area))


class PlanetaryComputerProvider:
    def __init__(self) -> None:
        settings = get_settings()
        modifier = planetary_computer.sign_inplace
        if settings.pc_subscription_key:
            modifier = lambda item: planetary_computer.sign_inplace(item, subscription_key=settings.pc_subscription_key)

        self.client = pystac_client.Client.open(settings.pc_stac_url, modifier=modifier)

    @staticmethod
    def _to_scene_result(item: Any, fallback_collection: str) -> SceneResult | None:
        assets = {key: asset.href for key, asset in item.assets.items()}
        dt = item.datetime
        if dt is None:
            return None
        preview_url = (
            assets.get("rendered_preview")
            or assets.get("preview")
            or assets.get("thumbnail")
            or assets.get("visual")
        )
        return SceneResult(
            scene_id=item.id,
            collection=item.collection_id or fallback_collection,
            acquisition_date=dt,
            cloud_cover=item.properties.get("eo:cloud_cover"),
            assets=assets,
            bbox=list(item.bbox) if item.bbox else None,
            footprint_geojson=item.geometry if isinstance(item.geometry, dict) else None,
            preview_url=preview_url,
        )

    def search_sentinel2(
        self,
        geometry: BaseGeometry,
        date_from: date,
        date_to: date,
        max_cloud: float,
    ) -> list[SceneResult]:
        date_range = f"{date_from.isoformat()}/{date_to.isoformat()}"
        search = self.client.search(
            collections=["sentinel-2-l2a"],
            intersects=mapping(geometry),
            datetime=date_range,
            query={"eo:cloud_cover": {"lte": max_cloud}},
            sortby=[{"field": "properties.datetime", "direction": "desc"}],
            max_items=20,
        )
        results: list[SceneResult] = []
        for item in search.items():
            parsed = self._to_scene_result(item=item, fallback_collection="sentinel-2-l2a")
            if parsed is not None:
                results.append(parsed)
        return results

    def get_scene_by_id(self, scene_id: str, collection: str = "sentinel-2-l2a") -> SceneResult | None:
        search = self.client.search(collections=[collection], ids=[scene_id], max_items=1)
        for item in search.items():
            parsed = self._to_scene_result(item=item, fallback_collection=collection)
            if parsed is not None:
                return parsed
        return None

    def search_sentinel1_rtc(self, geometry: BaseGeometry, date_from: date, date_to: date) -> list[SceneResult]:
        date_range = f"{date_from.isoformat()}/{date_to.isoformat()}"
        search = self.client.search(
            collections=["sentinel-1-rtc"],
            intersects=mapping(geometry),
            datetime=date_range,
            sortby=[{"field": "properties.datetime", "direction": "desc"}],
            max_items=20,
        )
        results: list[SceneResult] = []
        for item in search.items():
            parsed = self._to_scene_result(item=item, fallback_collection="sentinel-1-rtc")
            if parsed is not None:
                parsed.cloud_cover = None
                results.append(parsed)
        return results
