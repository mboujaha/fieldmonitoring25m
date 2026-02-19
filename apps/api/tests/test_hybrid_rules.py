from app.services.indices import INDEX_REQUIREMENTS


def test_band_requirements_locked() -> None:
    assert INDEX_REQUIREMENTS["NDVI"] == ("B08", "B04")
    assert INDEX_REQUIREMENTS["NDMI"] == ("B08", "B11")
    assert INDEX_REQUIREMENTS["NDWI"] == ("B03", "B08")
