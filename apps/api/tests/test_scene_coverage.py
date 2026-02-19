from datetime import datetime, timezone

from shapely.geometry import Polygon

from app.services.planetary_computer import SceneResult, scene_field_coverage_ratio, scene_to_geometry


def _scene(footprint_geojson: dict | None = None, bbox: list[float] | None = None) -> SceneResult:
    return SceneResult(
        scene_id="S2A_TEST",
        collection="sentinel-2-l2a",
        acquisition_date=datetime(2026, 2, 19, 12, 0, tzinfo=timezone.utc),
        cloud_cover=12.0,
        assets={},
        bbox=bbox,
        footprint_geojson=footprint_geojson,
    )


def test_scene_to_geometry_prefers_stac_footprint() -> None:
    scene = _scene(
        footprint_geojson={
            "type": "Polygon",
            "coordinates": [[[-1, -1], [2, -1], [2, 2], [-1, 2], [-1, -1]]],
        },
        bbox=[100, 100, 101, 101],
    )
    geometry = scene_to_geometry(scene)
    assert geometry is not None
    assert tuple(geometry.bounds) == (-1.0, -1.0, 2.0, 2.0)


def test_scene_field_coverage_ratio_full_coverage_from_bbox() -> None:
    field = Polygon([[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]])
    scene = _scene(bbox=[-1, -1, 2, 2])
    ratio = scene_field_coverage_ratio(scene=scene, field_geometry=field)
    assert ratio == 1.0


def test_scene_field_coverage_ratio_partial() -> None:
    field = Polygon([[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]])
    scene = _scene(
        footprint_geojson={
            "type": "Polygon",
            "coordinates": [[[0.5, 0], [1.5, 0], [1.5, 1], [0.5, 1], [0.5, 0]]],
        }
    )
    ratio = scene_field_coverage_ratio(scene=scene, field_geometry=field)
    assert ratio == 0.5
