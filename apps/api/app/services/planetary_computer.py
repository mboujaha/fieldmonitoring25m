from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from urllib.parse import urlparse, urlunparse
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen
import json

try:
    import httpx
except ModuleNotFoundError:  # optional on older worker images
    httpx = None
try:
    import planetary_computer
except ModuleNotFoundError:  # optional on older worker images
    planetary_computer = None
try:
    import pystac_client
except ModuleNotFoundError:  # optional on older worker images
    pystac_client = None
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
        self.settings = get_settings()
        self._token_cache: dict[str, str] = {}
        self.client = None
        if pystac_client is None:
            return

        modifier = None
        if planetary_computer is not None:
            modifier = planetary_computer.sign_inplace
            if self.settings.pc_subscription_key:
                modifier = lambda item: planetary_computer.sign_inplace(item, subscription_key=self.settings.pc_subscription_key)
        self.client = pystac_client.Client.open(self.settings.pc_stac_url, modifier=modifier)

    def _sas_token_url(self, collection_id: str) -> str:
        parsed = urlparse(self.settings.pc_stac_url)
        path = parsed.path.rstrip("/")
        if "/stac/" in path:
            path = path.replace("/stac/", "/sas/", 1)
        else:
            path = "/api/sas/v1"
        token_path = f"{path}/token/{collection_id}"
        return urlunparse((parsed.scheme, parsed.netloc, token_path, "", "", ""))

    def _get_sas_token(self, collection_id: str) -> str | None:
        cached = self._token_cache.get(collection_id)
        if cached:
            return cached

        headers: dict[str, str] = {}
        if self.settings.pc_subscription_key:
            headers["Ocp-Apim-Subscription-Key"] = self.settings.pc_subscription_key

        try:
            if httpx is not None:
                response = httpx.get(self._sas_token_url(collection_id), headers=headers, timeout=15.0)
                response.raise_for_status()
                payload = response.json()
            else:
                request = Request(self._sas_token_url(collection_id), headers=headers, method="GET")
                with urlopen(request, timeout=15.0) as response:
                    payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            return None

        token = (
            payload.get("token")
            or payload.get("sasToken")
            or payload.get("sas")
            or payload.get("query")
        )
        if not isinstance(token, str) or not token.strip():
            return None

        normalized = token.lstrip("?")
        self._token_cache[collection_id] = normalized
        return normalized

    def _maybe_sign_assets(self, assets: dict[str, str], collection_id: str) -> dict[str, str]:
        if planetary_computer is not None:
            return assets

        token = self._get_sas_token(collection_id)
        if not token:
            return assets

        signed: dict[str, str] = {}
        for key, href in assets.items():
            if "?" in href:
                signed[key] = href
            else:
                signed[key] = f"{href}?{token}"
        return signed

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None

    def _to_scene_result(self, item: Any, fallback_collection: str) -> SceneResult | None:
        if isinstance(item, dict):
            assets = {
                key: href
                for key, href in (
                    (asset_key, (asset_payload or {}).get("href"))
                    for asset_key, asset_payload in (item.get("assets") or {}).items()
                )
                if isinstance(href, str)
            }
            properties = item.get("properties") or {}
            dt = self._parse_datetime(properties.get("datetime"))
            if dt is None:
                return None
            collection_id = item.get("collection") or fallback_collection
            assets = self._maybe_sign_assets(assets, collection_id)
            preview_url = (
                assets.get("rendered_preview")
                or assets.get("preview")
                or assets.get("thumbnail")
                or assets.get("visual")
            )
            return SceneResult(
                scene_id=item.get("id", ""),
                collection=collection_id,
                acquisition_date=dt,
                cloud_cover=properties.get("eo:cloud_cover"),
                assets=assets,
                bbox=list(item["bbox"]) if isinstance(item.get("bbox"), list) else None,
                footprint_geojson=item.get("geometry") if isinstance(item.get("geometry"), dict) else None,
                preview_url=preview_url,
            )

        assets = {key: asset.href for key, asset in item.assets.items()}
        dt = item.datetime
        if dt is None:
            return None
        collection_id = item.collection_id or fallback_collection
        assets = self._maybe_sign_assets(assets, collection_id)
        preview_url = (
            assets.get("rendered_preview")
            or assets.get("preview")
            or assets.get("thumbnail")
            or assets.get("visual")
        )
        return SceneResult(
            scene_id=item.id,
            collection=collection_id,
            acquisition_date=dt,
            cloud_cover=item.properties.get("eo:cloud_cover"),
            assets=assets,
            bbox=list(item.bbox) if item.bbox else None,
            footprint_geojson=item.geometry if isinstance(item.geometry, dict) else None,
            preview_url=preview_url,
        )

    def _manual_search(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        endpoint = self.settings.pc_stac_url.rstrip("/") + "/search"
        headers = {"Content-Type": "application/json"}
        if self.settings.pc_subscription_key:
            headers["Ocp-Apim-Subscription-Key"] = self.settings.pc_subscription_key
        if httpx is not None:
            response = httpx.post(endpoint, json=payload, headers=headers, timeout=45.0)
            response.raise_for_status()
            body = response.json()
        else:
            data = json.dumps(payload).encode("utf-8")
            request = Request(endpoint, data=data, headers=headers, method="POST")
            try:
                with urlopen(request, timeout=45.0) as response:
                    body = json.loads(response.read().decode("utf-8"))
            except (HTTPError, URLError, ValueError):
                return []
        features = body.get("features")
        if isinstance(features, list):
            return [item for item in features if isinstance(item, dict)]
        return []

    def search_sentinel2(
        self,
        geometry: BaseGeometry,
        date_from: date,
        date_to: date,
        max_cloud: float,
    ) -> list[SceneResult]:
        date_range = f"{date_from.isoformat()}/{date_to.isoformat()}"
        results: list[SceneResult] = []
        if self.client is not None:
            search = self.client.search(
                collections=["sentinel-2-l2a"],
                intersects=mapping(geometry),
                datetime=date_range,
                query={"eo:cloud_cover": {"lte": max_cloud}},
                sortby=[{"field": "properties.datetime", "direction": "desc"}],
                max_items=20,
            )
            for item in search.items():
                parsed = self._to_scene_result(item=item, fallback_collection="sentinel-2-l2a")
                if parsed is not None:
                    results.append(parsed)
            return results

        features = self._manual_search(
            {
                "collections": ["sentinel-2-l2a"],
                "intersects": mapping(geometry),
                "datetime": date_range,
                "query": {"eo:cloud_cover": {"lte": max_cloud}},
                "sortby": [{"field": "properties.datetime", "direction": "desc"}],
                "limit": 20,
            }
        )
        for feature in features:
            parsed = self._to_scene_result(item=feature, fallback_collection="sentinel-2-l2a")
            if parsed is not None:
                results.append(parsed)
        return results

    def get_scene_by_id(self, scene_id: str, collection: str = "sentinel-2-l2a") -> SceneResult | None:
        if self.client is not None:
            search = self.client.search(collections=[collection], ids=[scene_id], max_items=1)
            for item in search.items():
                parsed = self._to_scene_result(item=item, fallback_collection=collection)
                if parsed is not None:
                    return parsed
            return None

        features = self._manual_search({"collections": [collection], "ids": [scene_id], "limit": 1})
        for feature in features:
            parsed = self._to_scene_result(item=feature, fallback_collection=collection)
            if parsed is not None:
                return parsed
        return None

    def search_sentinel1_rtc(self, geometry: BaseGeometry, date_from: date, date_to: date) -> list[SceneResult]:
        date_range = f"{date_from.isoformat()}/{date_to.isoformat()}"
        results: list[SceneResult] = []
        if self.client is not None:
            search = self.client.search(
                collections=["sentinel-1-rtc"],
                intersects=mapping(geometry),
                datetime=date_range,
                sortby=[{"field": "properties.datetime", "direction": "desc"}],
                max_items=20,
            )
            for item in search.items():
                parsed = self._to_scene_result(item=item, fallback_collection="sentinel-1-rtc")
                if parsed is not None:
                    parsed.cloud_cover = None
                    results.append(parsed)
            return results

        features = self._manual_search(
            {
                "collections": ["sentinel-1-rtc"],
                "intersects": mapping(geometry),
                "datetime": date_range,
                "sortby": [{"field": "properties.datetime", "direction": "desc"}],
                "limit": 20,
            }
        )
        for feature in features:
            parsed = self._to_scene_result(item=feature, fallback_collection="sentinel-1-rtc")
            if parsed is not None:
                parsed.cloud_cover = None
                results.append(parsed)
        return results
