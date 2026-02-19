import pytest

from app.services.geometry import area_hectares, enforce_area_limit, parse_geojson_geometry


def test_parse_geojson_polygon_into_multipolygon() -> None:
    geometry = {
        "type": "Polygon",
        "coordinates": [
            [
                [-6.0, 34.0],
                [-5.99, 34.0],
                [-5.99, 34.01],
                [-6.0, 34.01],
                [-6.0, 34.0],
            ]
        ],
    }
    shape = parse_geojson_geometry(geometry)
    assert shape.geom_type == "MultiPolygon"
    assert area_hectares(shape) > 0


def test_enforce_area_limit_raises() -> None:
    with pytest.raises(ValueError):
        enforce_area_limit(20_000)
