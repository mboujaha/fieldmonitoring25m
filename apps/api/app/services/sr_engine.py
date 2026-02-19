from __future__ import annotations

import json
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

try:
    import httpx
except ModuleNotFoundError:  # optional on older worker images
    httpx = None
import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry

from app.core.config import Settings, get_settings

SR4RS_MODEL_URL_CURRENT = (
    "https://nextcloud.inrae.fr/s/boabW9yCjdpLPGX/download/"
    "sr4rs_sentinel2_bands4328_france2020_savedmodel.zip"
)
SR4RS_MODEL_URL_LEGACY = (
    "https://nextcloud.inrae.fr/s/6xM4jRzYx2A9Qn4/download"
    "?path=%2F&files=sr4rs_sentinel2_bands4328_france2020_savedmodel.zip"
)


class SRInferenceError(RuntimeError):
    pass


@dataclass
class SRCapabilities:
    model_name: str
    model_version: str
    supported_bands: set[str]
    scale_factor: int
    runtime_class: str


@dataclass
class SRRequest:
    acquisition_date: date
    aoi_geometry: BaseGeometry
    native_bands: dict[str, np.ndarray]
    source_assets: dict[str, str]


class BaseSREngine:
    def get_capabilities(self) -> SRCapabilities:
        raise NotImplementedError

    def generate(self, request: SRRequest) -> dict[str, np.ndarray]:
        raise NotImplementedError


def _parse_band_order(value: str) -> list[str]:
    return [band.strip() for band in value.split(",") if band.strip()]


def _write_stacked_tiff(path: Path, bands: dict[str, np.ndarray], order: list[str]) -> None:
    arrays = [bands[name].astype(np.float32) for name in order]
    if not arrays:
        raise SRInferenceError("No input bands provided for SR stack")

    height, width = arrays[0].shape
    for arr in arrays:
        if arr.shape != (height, width):
            raise SRInferenceError("All SR input bands must share the same shape")

    transform = from_origin(0.0, 0.0, 1.0, 1.0)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=len(order),
        dtype=np.float32,
        crs="EPSG:4326",
        transform=transform,
    ) as dataset:
        for idx, arr in enumerate(arrays, start=1):
            dataset.write(arr, idx)


def _read_multiband_tiff(path: Path, band_order: list[str]) -> dict[str, np.ndarray]:
    with rasterio.open(path) as dataset:
        count = min(dataset.count, len(band_order))
        if count == 0:
            raise SRInferenceError("SR output raster has zero bands")
        out: dict[str, np.ndarray] = {}
        for idx in range(count):
            out[band_order[idx]] = dataset.read(idx + 1).astype(np.float32)
        return out


def _read_multiband_memory(payload: bytes, band_order: list[str]) -> dict[str, np.ndarray]:
    with MemoryFile(payload) as memfile:
        with memfile.open() as dataset:
            count = min(dataset.count, len(band_order))
            if count == 0:
                raise SRInferenceError("SR output raster has zero bands")
            out: dict[str, np.ndarray] = {}
            for idx in range(count):
                out[band_order[idx]] = dataset.read(idx + 1).astype(np.float32)
            return out


class SR4RSInferenceEngine(BaseSREngine):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.input_order = ["B04", "B03", "B02", "B08"]
        self.output_order = ["B04", "B03", "B02", "B08"]
        self.script_path = Path(settings.sr4rs_script_path)
        self.model_dir = Path(settings.sr4rs_model_dir)
        self.model_url = settings.sr4rs_model_url
        self.timeout_seconds = settings.sr4rs_timeout_seconds
        self.python_executable = settings.sr4rs_python_executable
        self._capabilities = SRCapabilities(
            model_name="sr4rs",
            model_version="bands4328-france2020",
            supported_bands=set(self.output_order),
            scale_factor=max(int(settings.sr4rs_scale_factor), 1),
            runtime_class="GPU",
        )

    def _candidate_model_urls(self) -> list[str]:
        candidates: list[str] = []
        configured = (self.model_url or "").strip()
        if configured:
            candidates.append(configured)
        for fallback in [SR4RS_MODEL_URL_CURRENT, SR4RS_MODEL_URL_LEGACY]:
            if fallback not in candidates:
                candidates.append(fallback)
        return candidates

    def get_capabilities(self) -> SRCapabilities:
        return self._capabilities

    def _find_saved_model_dir(self, root: Path) -> Path | None:
        if not root.exists():
            return None
        candidates = [path.parent for path in root.rglob("saved_model.pb")]
        if not candidates:
            return None
        candidates.sort(key=lambda p: len(str(p)))
        return candidates[0]

    def _ensure_model(self) -> Path:
        if (self.model_dir / "saved_model.pb").exists():
            return self.model_dir

        existing = self._find_saved_model_dir(self.model_dir)
        if existing:
            self.model_dir = existing
            return existing

        self.model_dir.parent.mkdir(parents=True, exist_ok=True)
        errors: list[str] = []
        for candidate_url in self._candidate_model_urls():
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_file:
                zip_path = Path(tmp_file.name)

            try:
                if httpx is not None:
                    with httpx.Client(timeout=self.timeout_seconds) as client:
                        response = client.get(candidate_url)
                        response.raise_for_status()
                        zip_path.write_bytes(response.content)
                else:
                    request = Request(candidate_url, method="GET")
                    with urlopen(request, timeout=self.timeout_seconds) as response:
                        zip_path.write_bytes(response.read())
            except Exception as exc:
                errors.append(f"{candidate_url} ({exc})")
                zip_path.unlink(missing_ok=True)
                continue

            try:
                with zipfile.ZipFile(zip_path) as archive:
                    archive.extractall(self.model_dir.parent)
            except Exception as exc:
                errors.append(f"{candidate_url} (invalid archive: {exc})")
                zip_path.unlink(missing_ok=True)
                continue
            finally:
                zip_path.unlink(missing_ok=True)

            extracted = self._find_saved_model_dir(self.model_dir.parent)
            if extracted:
                self.model_dir = extracted
                return extracted
            errors.append(f"{candidate_url} (saved_model.pb not found after extraction)")

        raise SRInferenceError(
            "Could not download/load SR4RS model. "
            f"Tried URLs: {', '.join(self._candidate_model_urls())}. "
            f"Errors: {' | '.join(errors) if errors else 'unknown'}"
        )

    def generate(self, request: SRRequest) -> dict[str, np.ndarray]:
        missing = [band for band in self.input_order if band not in request.native_bands]
        if missing:
            raise SRInferenceError(f"SR4RS requires bands {self.input_order}; missing: {missing}")

        if not self.script_path.exists():
            raise SRInferenceError(
                f"SR4RS script not found at {self.script_path}. "
                "Ensure worker-gpu image includes /opt/sr4rs or set SR4RS_SCRIPT_PATH."
            )

        model_dir = self._ensure_model()

        with tempfile.TemporaryDirectory(prefix="sr4rs_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            input_path = tmp_path / "input.tif"
            output_path = tmp_path / "output.tif"

            _write_stacked_tiff(input_path, request.native_bands, self.input_order)

            command = [
                self.python_executable,
                str(self.script_path),
                "--savedmodel",
                str(model_dir),
                "--input",
                str(input_path),
                "--output",
                str(output_path),
            ]

            try:
                completed = subprocess.run(
                    command,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                )
            except subprocess.CalledProcessError as exc:
                raise SRInferenceError(
                    "SR4RS inference failed. "
                    f"stdout={exc.stdout[-800:] if exc.stdout else ''} "
                    f"stderr={exc.stderr[-800:] if exc.stderr else ''}"
                ) from exc
            except subprocess.TimeoutExpired as exc:
                raise SRInferenceError("SR4RS inference timed out") from exc

            if not output_path.exists():
                raise SRInferenceError(
                    "SR4RS command completed without an output file. "
                    f"stdout={completed.stdout[-800:] if completed.stdout else ''}"
                )

            return _read_multiband_tiff(output_path, self.output_order)


class S2DR3ExternalProviderEngine(BaseSREngine):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.endpoint = settings.s2dr3_external_endpoint
        self.api_key = settings.s2dr3_external_api_key
        self.command_template = settings.s2dr3_command_template
        self.band_order = _parse_band_order(settings.s2dr3_band_order)
        self.timeout_seconds = settings.s2dr3_timeout_seconds
        self._capabilities = SRCapabilities(
            model_name="s2dr3-external",
            model_version="external",
            supported_bands=set(self.band_order),
            scale_factor=max(int(settings.s2dr3_scale_factor), 1),
            runtime_class="EXTERNAL",
        )

    def get_capabilities(self) -> SRCapabilities:
        return self._capabilities

    def _via_http(self, request: SRRequest) -> dict[str, np.ndarray]:
        if not self.endpoint:
            raise SRInferenceError("S2DR3_EXTERNAL_ENDPOINT is not set")

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload: dict[str, Any] = {
            "date": request.acquisition_date.isoformat(),
            "aoi_geojson": mapping(request.aoi_geometry),
            "requested_bands": self.band_order,
            "source_assets": request.source_assets,
        }

        if httpx is not None:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(self.endpoint, json=payload, headers=headers)
                response.raise_for_status()
                body = response.json()

                if isinstance(body, dict) and isinstance(body.get("bands"), dict):
                    out: dict[str, np.ndarray] = {}
                    for band_name in self.band_order:
                        if band_name in body["bands"]:
                            out[band_name] = np.asarray(body["bands"][band_name], dtype=np.float32)
                    if out:
                        return out

                geotiff_url = body.get("geotiff_url") if isinstance(body, dict) else None
                if geotiff_url:
                    tif_response = client.get(geotiff_url, headers=headers)
                    tif_response.raise_for_status()
                    return _read_multiband_memory(tif_response.content, self.band_order)

                geotiff_path = body.get("geotiff_path") if isinstance(body, dict) else None
                if geotiff_path:
                    return _read_multiband_tiff(Path(geotiff_path), self.band_order)
        else:
            data = json.dumps(payload).encode("utf-8")
            post_request = Request(self.endpoint, data=data, headers=headers, method="POST")
            try:
                with urlopen(post_request, timeout=self.timeout_seconds) as response:
                    body = json.loads(response.read().decode("utf-8"))
            except (HTTPError, URLError, ValueError) as exc:
                raise SRInferenceError(f"S2DR3 HTTP provider failed: {exc}") from exc

            if isinstance(body, dict) and isinstance(body.get("bands"), dict):
                out: dict[str, np.ndarray] = {}
                for band_name in self.band_order:
                    if band_name in body["bands"]:
                        out[band_name] = np.asarray(body["bands"][band_name], dtype=np.float32)
                if out:
                    return out

            geotiff_url = body.get("geotiff_url") if isinstance(body, dict) else None
            if geotiff_url:
                get_headers = {key: value for key, value in headers.items() if key.lower() != "content-type"}
                tif_request = Request(geotiff_url, headers=get_headers, method="GET")
                try:
                    with urlopen(tif_request, timeout=self.timeout_seconds) as response:
                        tif_payload = response.read()
                except (HTTPError, URLError) as exc:
                    raise SRInferenceError(f"S2DR3 GeoTIFF download failed: {exc}") from exc
                return _read_multiband_memory(tif_payload, self.band_order)

            geotiff_path = body.get("geotiff_path") if isinstance(body, dict) else None
            if geotiff_path:
                return _read_multiband_tiff(Path(geotiff_path), self.band_order)

        raise SRInferenceError(
            "S2DR3 external provider response is unsupported. "
            "Expected `bands`, `geotiff_url`, or `geotiff_path`."
        )

    def _via_command(self, request: SRRequest) -> dict[str, np.ndarray]:
        if not self.command_template:
            raise SRInferenceError("S2DR3_COMMAND_TEMPLATE is not set")

        bounds = request.aoi_geometry.bounds
        with tempfile.TemporaryDirectory(prefix="s2dr3_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            geojson_path = tmp_path / "aoi.geojson"
            output_path = tmp_path / "output.tif"

            geojson_path.write_text(
                json.dumps({"type": "Feature", "geometry": mapping(request.aoi_geometry), "properties": {}}),
                encoding="utf-8",
            )

            command = self.command_template.format(
                date=request.acquisition_date.isoformat(),
                geojson=str(geojson_path),
                output=str(output_path),
                bbox_w=bounds[0],
                bbox_s=bounds[1],
                bbox_e=bounds[2],
                bbox_n=bounds[3],
            )

            try:
                subprocess.run(
                    command,
                    shell=True,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                )
            except subprocess.CalledProcessError as exc:
                raise SRInferenceError(
                    "S2DR3 command failed. "
                    f"stdout={exc.stdout[-800:] if exc.stdout else ''} "
                    f"stderr={exc.stderr[-800:] if exc.stderr else ''}"
                ) from exc
            except subprocess.TimeoutExpired as exc:
                raise SRInferenceError("S2DR3 command timed out") from exc

            if not output_path.exists():
                candidates = list(tmp_path.rglob("*.tif")) + list(tmp_path.rglob("*.tiff"))
                if not candidates:
                    raise SRInferenceError("S2DR3 command completed without output GeoTIFF")
                output_path = candidates[0]

            return _read_multiband_tiff(output_path, self.band_order)

    def generate(self, request: SRRequest) -> dict[str, np.ndarray]:
        if self.endpoint:
            return self._via_http(request)
        if self.command_template:
            return self._via_command(request)
        raise SRInferenceError(
            "S2DR3 external mode selected but no integration is configured. "
            "Set S2DR3_EXTERNAL_ENDPOINT or S2DR3_COMMAND_TEMPLATE."
        )


class NearestNeighborSREngine(BaseSREngine):
    def __init__(self) -> None:
        self._capabilities = SRCapabilities(
            model_name="nearest-neighbor-debug",
            model_version="1.0",
            supported_bands={"B02", "B03", "B04", "B08"},
            scale_factor=2,
            runtime_class="CPU",
        )

    def get_capabilities(self) -> SRCapabilities:
        return self._capabilities

    def generate(self, request: SRRequest) -> dict[str, np.ndarray]:
        upscale = self._capabilities.scale_factor
        output: dict[str, np.ndarray] = {}
        for band_name, data in request.native_bands.items():
            if band_name not in self._capabilities.supported_bands:
                continue
            output[band_name] = np.repeat(np.repeat(data, upscale, axis=0), upscale, axis=1)
        return output


def build_sr_engine() -> BaseSREngine:
    settings = get_settings()
    provider = settings.sr_provider.strip().lower()

    if provider in {"sr4rs", "sr4rs_local"}:
        return SR4RSInferenceEngine(settings)
    if provider in {"s2dr3", "s2dr3_external"}:
        return S2DR3ExternalProviderEngine(settings)
    if provider == "nearest":
        return NearestNeighborSREngine()
    if provider == "disabled":
        raise SRInferenceError("SR provider is disabled")

    raise SRInferenceError(f"Unsupported SR_PROVIDER '{settings.sr_provider}'")
