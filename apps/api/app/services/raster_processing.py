from __future__ import annotations

from typing import Iterable

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform
from pyproj import Transformer


class RasterProcessingError(RuntimeError):
    pass


def _project_geometry(geom: BaseGeometry, src_crs) -> BaseGeometry:
    transformer = Transformer.from_crs("EPSG:4326", src_crs, always_xy=True)
    return transform(transformer.transform, geom)


def read_scene_patch(
    assets: dict[str, str],
    aoi_geometry: BaseGeometry,
    bands: Iterable[str],
    scl_asset_key: str = "SCL",
) -> tuple[dict[str, np.ndarray], np.ndarray, object, str]:
    band_list = list(bands)
    if not band_list:
        raise RasterProcessingError("No bands requested")

    reference_band = "B04" if "B04" in band_list else band_list[0]
    reference_href = assets.get(reference_band)
    if reference_href is None:
        raise RasterProcessingError(f"Reference band {reference_band} missing in assets")

    with rasterio.open(reference_href) as ref:
        geom_ref = _project_geometry(aoi_geometry, ref.crs)
        minx, miny, maxx, maxy = geom_ref.bounds
        window_ref = from_bounds(minx, miny, maxx, maxy, transform=ref.transform)
        window_ref = window_ref.round_offsets().round_lengths()
        ref_data = ref.read(1, window=window_ref, boundless=True, fill_value=np.nan).astype(np.float32)
        if ref_data.size == 0:
            raise RasterProcessingError("Empty raster window for AOI")
        ref_transform = ref.window_transform(window_ref)
        ref_crs = ref.crs.to_string()
        aoi_mask = geometry_mask(
            [geom_ref.__geo_interface__], out_shape=ref_data.shape, transform=ref_transform, invert=True
        )

    band_arrays: dict[str, np.ndarray] = {reference_band: ref_data}

    for band_name in band_list:
        if band_name == reference_band:
            continue
        href = assets.get(band_name)
        if href is None:
            continue
        with rasterio.open(href) as src:
            geom_src = _project_geometry(aoi_geometry, src.crs)
            minx, miny, maxx, maxy = geom_src.bounds
            window = from_bounds(minx, miny, maxx, maxy, transform=src.transform)
            window = window.round_offsets().round_lengths()
            data = src.read(
                1,
                window=window,
                out_shape=ref_data.shape,
                boundless=True,
                fill_value=np.nan,
                resampling=Resampling.bilinear,
            ).astype(np.float32)
            nodata = src.nodata
            if nodata is not None:
                data[data == nodata] = np.nan
            band_arrays[band_name] = data

    scl_data: np.ndarray | None = None
    scl_href = assets.get(scl_asset_key)
    if scl_href:
        with rasterio.open(scl_href) as src:
            geom_src = _project_geometry(aoi_geometry, src.crs)
            minx, miny, maxx, maxy = geom_src.bounds
            window = from_bounds(minx, miny, maxx, maxy, transform=src.transform)
            window = window.round_offsets().round_lengths()
            scl_data = src.read(
                1,
                window=window,
                out_shape=ref_data.shape,
                boundless=True,
                fill_value=0,
                resampling=Resampling.nearest,
            )

    valid_mask = aoi_mask.copy()
    finite_mask = np.isfinite(ref_data)
    valid_mask &= finite_mask

    if scl_data is not None:
        invalid_scl = np.isin(np.rint(scl_data).astype(int), [0, 1, 3, 8, 9, 10, 11])
        valid_mask &= ~invalid_scl

    return band_arrays, valid_mask, ref_transform, ref_crs
