from __future__ import annotations

from geoalchemy2.elements import WKBElement
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import MultiPolygon


def to_wkb_element(multi_polygon: MultiPolygon) -> WKBElement:
    return from_shape(multi_polygon, srid=4326)


def to_shape_from_wkb(value: WKBElement) -> MultiPolygon:
    shape = to_shape(value)
    if isinstance(shape, MultiPolygon):
        return shape
    # PostGIS can return polygon for single-part multipolygon. Normalize.
    return MultiPolygon([shape])
