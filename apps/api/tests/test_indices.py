import numpy as np

from app.services.indices import available_indices_for_bands, compute_indices


def test_compute_indices_core_outputs() -> None:
    bands = {
        "B02": np.array([[0.2, 0.2], [0.2, 0.2]], dtype=np.float32),
        "B03": np.array([[0.3, 0.3], [0.3, 0.3]], dtype=np.float32),
        "B04": np.array([[0.4, 0.4], [0.4, 0.4]], dtype=np.float32),
        "B05": np.array([[0.45, 0.45], [0.45, 0.45]], dtype=np.float32),
        "B08": np.array([[0.6, 0.6], [0.6, 0.6]], dtype=np.float32),
        "B11": np.array([[0.5, 0.5], [0.5, 0.5]], dtype=np.float32),
    }
    valid_mask = np.array([[True, True], [True, True]])

    result = compute_indices(bands=bands, valid_mask=valid_mask)

    assert "NDVI" in result
    assert "NDMI" in result
    assert "NDWI" in result
    assert "EVI" in result
    assert "NDRE" in result
    assert "SAVI" in result
    assert result["NDVI"]["stats"]["mean"] is not None


def test_available_indices_for_partial_band_set() -> None:
    bands = {"B02", "B03", "B04", "B08"}
    available = available_indices_for_bands(bands)
    assert "NDVI" in available
    assert "NDWI" in available
    assert "NDMI" not in available
