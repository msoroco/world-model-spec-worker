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


def bind(opendrive: Path, parcel_authority: Path, *, property_id: str,
         intersecting_street_id: str, connector_routes: dict,
         review: dict) -> dict:
    """Return a source-sealed packet for construction and saved observation."""
    _require(opendrive.is_file() and parcel_authority.is_file(), 'original map and parcel authority files required')
    _require(opendrive.suffix.lower() == '.xodr' and '<OpenDRIVE' in opendrive.read_text(), 'original OpenDRIVE source required')
    source = json.loads(parcel_authority.read_text())
    _require(source.get('format') == 'original-parcel-authority-v1', 'original parcel authority format required')
    _require(source.get('opendrive_sha256') == _sha(opendrive), 'parcel authority map seal differs')
    _require(source.get('coordinate_frame') and source.get('map_name'), 'source map identity and coordinates required')
    _require(review.get('reviewer') and review.get('source') and review.get('decision') == 'reviewed', 'explicit original authority review required')
    _require(source.get('intersecting_street_id') == intersecting_street_id, 'destination street authority differs')
    properties = source.get('properties', [])
    _require(isinstance(properties, list) and properties, 'parcel inventory required')
    ids = set()
    for item in properties:
        _require(item.get('id') and item['id'] not in ids, 'distinct source parcel identities required')
        ids.add(item['id'])
        _require(item.get('status') in ('private', 'public') and item.get('authority'), 'parcel classification and authority required')
        polygon = item.get('polygon_xy_m', [])
        _require(len(polygon) >= 3 and all(len(point) == 2 and all(math.isfinite(float(v)) for v in point) for point in polygon), 'finite original parcel polygon required')
    _require(property_id in ids, 'selected property absent from original authority')
    _require(property_id in connector_routes, 'selected connector route required')
    route = connector_routes[property_id]
    _require(len(route) >= 3 and all(len(point) == 2 and all(math.isfinite(float(v)) for v in point) for point in route), 'finite connector waypoints required')
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
    }
