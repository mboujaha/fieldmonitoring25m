from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


INDEX_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "NDVI": ("B08", "B04"),
    "NDMI": ("B08", "B11"),
    "NDWI": ("B03", "B08"),
    "EVI": ("B08", "B04", "B02"),
    "NDRE": ("B08", "B05"),
    "SAVI": ("B08", "B04"),
}


@dataclass
class IndexOutput:
    values: np.ndarray
    stats: dict[str, float | None]


def _safe_divide(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.divide(numerator, denominator)
    out[~np.isfinite(out)] = np.nan
    return out


def _stats(arr: np.ndarray) -> dict[str, float | None]:
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return {"min": None, "max": None, "mean": None, "p10": None, "p90": None}
    return {
        "min": float(np.nanmin(finite)),
        "max": float(np.nanmax(finite)),
        "mean": float(np.nanmean(finite)),
        "p10": float(np.nanpercentile(finite, 10)),
        "p90": float(np.nanpercentile(finite, 90)),
    }


def _normalize_reflectance(arr: np.ndarray) -> np.ndarray:
    arr = arr.astype(np.float32)
    if np.nanmax(arr) > 2.0:
        arr = arr / 10000.0
    return arr


def compute_index_rasters(bands: dict[str, np.ndarray], valid_mask: np.ndarray | None = None) -> dict[str, np.ndarray]:
    normalized = {name: _normalize_reflectance(value) for name, value in bands.items()}
    if not normalized:
        return {}
    shape = next(iter(normalized.values())).shape
    mask = np.ones(shape, dtype=bool) if valid_mask is None else valid_mask.copy()

    out: dict[str, np.ndarray] = {}

    if {"B08", "B04"}.issubset(normalized):
        ndvi = _safe_divide(normalized["B08"] - normalized["B04"], normalized["B08"] + normalized["B04"])
        ndvi[~mask] = np.nan
        out["NDVI"] = ndvi

        savi = _safe_divide(1.5 * (normalized["B08"] - normalized["B04"]), normalized["B08"] + normalized["B04"] + 0.5)
        savi[~mask] = np.nan
        out["SAVI"] = savi

    if {"B08", "B11"}.issubset(normalized):
        ndmi = _safe_divide(normalized["B08"] - normalized["B11"], normalized["B08"] + normalized["B11"])
        ndmi[~mask] = np.nan
        out["NDMI"] = ndmi

    if {"B03", "B08"}.issubset(normalized):
        ndwi = _safe_divide(normalized["B03"] - normalized["B08"], normalized["B03"] + normalized["B08"])
        ndwi[~mask] = np.nan
        out["NDWI"] = ndwi

    if {"B08", "B04", "B02"}.issubset(normalized):
        evi = _safe_divide(
            2.5 * (normalized["B08"] - normalized["B04"]),
            normalized["B08"] + 6 * normalized["B04"] - 7.5 * normalized["B02"] + 1,
        )
        evi[~mask] = np.nan
        out["EVI"] = evi

    if {"B08", "B05"}.issubset(normalized):
        ndre = _safe_divide(normalized["B08"] - normalized["B05"], normalized["B08"] + normalized["B05"])
        ndre[~mask] = np.nan
        out["NDRE"] = ndre

    return out


def compute_indices(bands: dict[str, np.ndarray], valid_mask: np.ndarray | None = None) -> dict[str, dict[str, Any]]:
    rasters = compute_index_rasters(bands=bands, valid_mask=valid_mask)
    return {name: {"stats": _stats(values)} for name, values in rasters.items()}


def compute_valid_pixel_ratio(valid_mask: np.ndarray) -> float:
    total = valid_mask.size
    if total == 0:
        return 0.0
    return float(np.sum(valid_mask) / total)


def available_indices_for_bands(bands: set[str]) -> list[str]:
    available: list[str] = []
    for index_name, required in INDEX_REQUIREMENTS.items():
        if set(required).issubset(bands):
            available.append(index_name)
    return sorted(available)
