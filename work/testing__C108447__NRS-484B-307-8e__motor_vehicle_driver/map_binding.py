"""Bind an original OpenDRIVE map to a separately reviewed parcel source.

The parcel authority is an external input. This code verifies its seals and
coordinate agreement; it cannot establish that an authority's claims are true.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def _inside(point: tuple[float, float], polygon: list[list[float]]) -> bool:
    x, y = point
    inside = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
            inside = not inside
    return inside


def _crosses_interior(route: list[list[float]], polygon: list[list[float]]) -> bool:
    for start, end in zip(route, route[1:]):
        cuts = [0.0, 1.0]
        dx, dy = end[0] - start[0], end[1] - start[1]
        for a, b in zip(polygon, polygon[1:] + polygon[:1]):
            ex, ey = b[0] - a[0], b[1] - a[1]
            denominator = dx * ey - dy * ex
            if abs(denominator) < 1e-10:
                continue
            rx, ry = a[0] - start[0], a[1] - start[1]
            t = (rx * ey - ry * ex) / denominator
            u = (rx * dy - ry * dx) / denominator
            if 0 <= t <= 1 and 0 <= u <= 1:
                cuts.append(t)
        cuts = sorted(set(cuts))
        for lo, hi in zip(cuts, cuts[1:]):
            if hi - lo > 1e-8 and _inside((start[0] + dx * (lo + hi) / 2,
                                          start[1] + dy * (lo + hi) / 2), polygon):
                return True
    return False


def bind(opendrive: Path, parcel_authority: Path, *, property_id: str,
         intersecting_street_id: str, connector_routes: dict,
         review: dict, roadway_route: list | None = None) -> dict:
    """Return a source-sealed packet for construction and saved observation."""
    _require(opendrive.is_file() and parcel_authority.is_file(), 'original map and parcel authority files required')
    _require(opendrive.suffix.lower() == '.xodr' and '<OpenDRIVE' in opendrive.read_text(), 'original OpenDRIVE source required')
    source = json.loads(parcel_authority.read_text())
    _require(source.get('format') == 'original-parcel-authority-v1', 'original parcel authority format required')
    _require(source.get('opendrive_sha256') == _sha(opendrive), 'parcel authority map seal differs')
    _require(source.get('coordinate_frame') and source.get('map_name'), 'source map identity and coordinates required')
    _require(review.get('reviewer') and review.get('source') and review.get('decision') == 'reviewed', 'explicit original authority review required')
    _require(source.get('intersecting_street_id') == intersecting_street_id, 'destination street authority differs')
    _require(source.get('connector_routes') == connector_routes,
             'connector route differs from sealed original authority')
    if roadway_route is not None:
        _require(source.get('roadway_route') == roadway_route,
                 'ordinary roadway route differs from sealed original authority')
    properties = source.get('properties', [])
    _require(isinstance(properties, list) and properties, 'parcel inventory required')
    ids = set()
    for item in properties:
        _require(item.get('id') and item['id'] not in ids, 'distinct source parcel identities required')
        ids.add(item['id'])
        _require(item.get('status') in ('private', 'public') and item.get('authority'), 'parcel classification and authority required')
        polygon = item.get('polygon_xy_m', [])
        _require(len(polygon) >= 3 and all(len(point) == 2 and all(math.isfinite(float(v)) for v in point) for point in polygon), 'finite original parcel polygon required')
        double_area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(polygon, polygon[1:] + polygon[:1]))
        _require(abs(double_area) > 1e-8, 'nondegenerate original parcel polygon required')
    _require(property_id in ids, 'selected property absent from original authority')
    _require(property_id in connector_routes, 'selected connector route required')
    route = connector_routes[property_id]
    _require(len(route) >= 3 and all(len(point) == 2 and all(math.isfinite(float(v)) for v in point) for point in route), 'finite connector waypoints required')
    selected = next(item for item in properties if item['id'] == property_id)
    _require(_crosses_interior(route, selected['polygon_xy_m']), 'connector does not traverse selected property')
    if roadway_route is not None:
        _require(len(roadway_route) >= 3 and all(len(point) == 2 and all(math.isfinite(float(v)) for v in point) for point in roadway_route),
                 'finite source roadway waypoints required')
        _require(all(not _crosses_interior(roadway_route, item['polygon_xy_m']) for item in properties),
                 'ordinary roadway route traverses classified property')
    return {
        'source': {'kind': 'original_native_map_and_property_authority',
                   'path': str(parcel_authority.resolve()), 'sha256': _sha(parcel_authority)},
        'native_map': {'path': str(opendrive.resolve()), 'sha256': _sha(opendrive),
                       'map_name': source['map_name']},
        'authority_review': review,
        'coordinate_frame': source['coordinate_frame'],
        'intersecting_street_id': intersecting_street_id,
        'properties': properties,
        'connector_routes': connector_routes,
        'roadway_route': roadway_route,
    }
