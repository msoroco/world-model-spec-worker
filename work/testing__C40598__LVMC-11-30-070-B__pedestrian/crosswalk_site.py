"""Source-gated geometry and context for LVMC 11.30.070(B).

All coordinates and frontage measurements must come from an independently
reviewed original site packet. This module never assigns a legal verdict.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT = 'testing__C40598__LVMC-11-30-070-B__pedestrian'
REQUIRED_SOURCES = {'opendrive', 'roadway', 'crosswalk_inventory',
                    'pedestrian_route', 'district_frontage', 'governing_controls',
                    'cameras'}
CAMERAS = {'overview', 'approach', 'reference_corner', 'driver_reference'}


def _point(value: object) -> tuple[float, float]:
    if (not isinstance(value, (list, tuple)) or len(value) != 2 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
        raise ValueError('finite original XY point required')
    return float(value[0]), float(value[1])


def _polygon(value: object) -> list[tuple[float, float]]:
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError('original polygon requires at least three vertices')
    return [_point(vertex) for vertex in value]


def _on_segment(point: tuple[float, float], a: tuple[float, float],
                b: tuple[float, float]) -> bool:
    cross = (point[0] - a[0]) * (b[1] - a[1]) - (point[1] - a[1]) * (b[0] - a[0])
    return (abs(cross) <= 1e-9 and
            min(a[0], b[0]) - 1e-9 <= point[0] <= max(a[0], b[0]) + 1e-9 and
            min(a[1], b[1]) - 1e-9 <= point[1] <= max(a[1], b[1]) + 1e-9)


def point_in_polygon(point: object, polygon: object) -> bool:
    """Count polygon boundaries as inside, avoiding a false outside crossing."""
    p = _point(point)
    vertices = _polygon(polygon)
    inside = False
    for a, b in zip(vertices, vertices[1:] + vertices[:1]):
        if _on_segment(p, a, b):
            return True
        if (a[1] > p[1]) != (b[1] > p[1]):
            edge_x = a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if p[0] < edge_x:
                inside = not inside
    return inside


def _segments_intersect(a, b, c, d) -> bool:
    def cross(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    aa, ab = cross(a, b, c), cross(a, b, d)
    ba, bb = cross(c, d, a), cross(c, d, b)
    if any(abs(v) <= 1e-9 for v in (aa, ab, ba, bb)):
        return any(_on_segment(p, u, v) for p, u, v in
                   ((a, c, d), (b, c, d), (c, a, b), (d, a, b)))
    return (aa > 0) != (ab > 0) and (ba > 0) != (bb > 0)


def polygons_intersect(first: object, second: object) -> bool:
    """Include edge contact; a pedestrian body touching a crosswalk is overlap."""
    a, b = _polygon(first), _polygon(second)
    if any(point_in_polygon(p, b) for p in a) or any(point_in_polygon(p, a) for p in b):
        return True
    return any(_segments_intersect(u, v, x, y)
               for u, v in zip(a, a[1:] + a[:1])
               for x, y in zip(b, b[1:] + b[:1]))


def classify_body(body_polygon: object, inventory: dict) -> dict:
    """Measure both categories separately; do not turn their union into a label."""
    if not isinstance(inventory, dict):
        raise ValueError('original crosswalk inventory missing')
    output = {}
    for category, field in (('marked', 'marked_crosswalk_polygons_xy_m'),
                            ('unmarked', 'unmarked_intersection_crosswalk_polygons_xy_m')):
        polygons = inventory.get(field)
        if not isinstance(polygons, list):
            raise ValueError('original ' + field + ' missing')
        output[category] = any(polygons_intersect(body_polygon, polygon)
                               for polygon in polygons)
    return output


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_review(packet_path: str | Path, source_root: str | Path, case_id: str) -> dict:
    """Reject absent, altered or merely diagnostic business-district sources."""
    packet_path, source_root = Path(packet_path).resolve(), Path(source_root).resolve()
    packet = json.loads(packet_path.read_text())
    if (packet.get('assignment_id') != ASSIGNMENT or packet.get('case_id') != case_id
            or packet.get('cell_id') != 'C40598'):
        raise ValueError('reviewed C40598 source identity differs')
    provenance = packet.get('source_provenance', {})
    if (provenance.get('kind') != 'original_reviewed_site' or
            provenance.get('diagnostic_fixture') is not False or
            not provenance.get('reviewer') or not provenance.get('citation')):
        raise ValueError('independently reviewed original site provenance required')
    sources = packet.get('sources')
    if not isinstance(sources, dict) or not REQUIRED_SOURCES <= sources.keys():
        raise ValueError('business-district source inventory incomplete')
    loaded = {}
    for name in REQUIRED_SOURCES:
        item = sources[name]
        if not isinstance(item, dict) or not item.get('path') or not item.get('sha256'):
            raise ValueError('reviewed source binding missing: ' + name)
        path = (source_root / item['path']).resolve()
        if not path.is_relative_to(source_root) or not path.is_file():
            raise ValueError('reviewed source path invalid: ' + name)
        if _sha(path) != item['sha256']:
            raise ValueError('reviewed source hash differs: ' + name)
        loaded[name] = path.read_text() if name == 'opendrive' else json.loads(path.read_text())
    roadway, inventory = loaded['roadway'], loaded['crosswalk_inventory']
    route, district = loaded['pedestrian_route'], loaded['district_frontage']
    if (not roadway.get('roadway_id') or not roadway.get('roadway_polygon_xy_m') or
            not roadway.get('intersection_polygons_xy_m') or
            not roadway.get('public_access_source') or
            not roadway.get('jurisdiction_source')):
        raise ValueError('reviewed roadway, public-access, jurisdiction and intersection source required')
    _polygon(roadway['roadway_polygon_xy_m'])
    for polygon in roadway['intersection_polygons_xy_m']:
        _polygon(polygon)
    if (inventory.get('roadway_id') != roadway['roadway_id'] or
            not inventory.get('classification_method')):
        raise ValueError('reviewed crosswalk classification source required')
    for field in ('marked_crosswalk_polygons_xy_m',
                  'unmarked_intersection_crosswalk_polygons_xy_m'):
        if not isinstance(inventory.get(field), list):
            raise ValueError('both crosswalk categories required')
        for polygon in inventory[field]:
            _polygon(polygon)
    if (route.get('roadway_id') != roadway['roadway_id'] or
            not route.get('pedestrian_actor_id') or
            not route.get('approach_xy_m') or not route.get('exit_xy_m') or
            not route.get('crossing_point_xy_m') or not route.get('route_xy_m')):
        raise ValueError('reviewed complete pedestrian crossing route required')
    if not point_in_polygon(route['crossing_point_xy_m'], roadway['roadway_polygon_xy_m']):
        raise ValueError('pedestrian crossing point is not in reviewed roadway')
    for point in route['route_xy_m']:
        _point(point)
    if (district.get('roadway_id') != roadway['roadway_id'] or
            district.get('highway_span_ft') != 600 or
            district.get('reading_assumption') is None or
            district.get('district_type') != 'business' or
            not isinstance(district.get('building_frontages'), list) or
            not district.get('both_frontage_alternatives_reviewed')):
        raise ValueError('reviewed 600-foot business-district frontage context required')
    for frontage in district['building_frontages']:
        if (frontage.get('use') not in ('business', 'industrial', 'other') or
                type(frontage.get('occupied_frontage_ft')) not in (int, float) or
                frontage['occupied_frontage_ft'] < 0 or
                not frontage.get('side')):
            raise ValueError('reviewed building use, side and frontage feet required')
    controls = loaded['governing_controls']
    if (controls.get('roadway_id') != roadway['roadway_id'] or
            not isinstance(controls.get('signs'), list) or
            not isinstance(controls.get('signals'), list)):
        raise ValueError('reviewed governing signs and signals required')
    cameras = loaded['cameras']
    if not isinstance(cameras, dict) or set(cameras) != CAMERAS:
        raise ValueError('four reviewed original camera poses required')
    for pose in cameras.values():
        if (not isinstance(pose, dict) or len(pose.get('location_xyz_m', [])) != 3 or
                len(pose.get('pitch_yaw_roll_deg', [])) != 3):
            raise ValueError('reviewed camera pose invalid')
    return {'review': packet, 'packet_sha256': _sha(packet_path),
            'sources': loaded, 'source_root': str(source_root)}
