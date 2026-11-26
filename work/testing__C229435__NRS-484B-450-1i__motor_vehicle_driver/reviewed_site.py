"""Gate a reviewed original railroad site before any Native world mutation."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from rail_proximity import _point, _segment_distance

ASSIGNMENT = 'testing__C229435__NRS-484B-450-1i__motor_vehicle_driver'
REQUIRED = {'opendrive', 'rail_inventory', 'ego_plan', 'other_vehicle_plan',
            'exception_review', 'cameras'}
CAMERAS = {'overview', 'approach', 'reference_corner', 'driver_reference'}
EXCEPTIONS = ('traffic_conflict_necessity', 'law_compliance',
              'officer_direction', 'official_device_direction')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def nearest_distance(footprint: list, rails: list) -> float:
    if not isinstance(footprint, list) or len(footprint) < 3:
        raise ValueError('complete original planned vehicle footprint required')
    polygon = [_point(p) for p in footprint]
    distances = []
    for rail in rails:
        if not isinstance(rail, dict) or not rail.get('rail_id') or not isinstance(rail.get('points_m'), list) or len(rail['points_m']) < 2:
            raise ValueError('reviewed railroad rail identity and polyline required')
        points = [_point(p) for p in rail['points_m']]
        distances.append(min(_segment_distance(polygon[i], polygon[(i + 1) % len(polygon)], points[j], points[j + 1])
                             for i in range(len(polygon)) for j in range(len(points) - 1)))
    if not distances:
        raise ValueError('nearest original railroad rail inventory empty')
    return min(distances)


def load_review(packet: str | Path, source_root: str | Path, case_id: str, target_m: float) -> dict:
    packet, source_root = Path(packet).resolve(), Path(source_root).resolve()
    review = json.loads(packet.read_text())
    if (review.get('assignment_id') != ASSIGNMENT or review.get('case_id') != case_id
            or review.get('cell_id') != 'C229435'):
        raise ValueError('reviewed railroad source identity differs')
    provenance = review.get('source_provenance', {})
    if (provenance.get('kind') != 'original_reviewed_site'
            or provenance.get('diagnostic_fixture') is not False
            or not provenance.get('reviewer') or not provenance.get('citation')):
        raise ValueError('external original railroad site review required')
    sources = review.get('sources')
    if not isinstance(sources, dict) or not REQUIRED <= set(sources):
        raise ValueError('reviewed railroad source inventory incomplete')
    loaded = {}
    for name in sorted(REQUIRED):
        item = sources[name]
        if not isinstance(item, dict) or not item.get('path') or not item.get('sha256'):
            raise ValueError('reviewed railroad source binding missing: ' + name)
        path = (source_root / item['path']).resolve()
        if not path.is_relative_to(source_root) or not path.is_file() or sha(path) != item['sha256']:
            raise ValueError('reviewed railroad source path/hash differs: ' + name)
        loaded[name] = path.read_text() if name == 'opendrive' else json.loads(path.read_text())
    rails, ego, other, context = (loaded[k] for k in
                                  ('rail_inventory', 'ego_plan', 'other_vehicle_plan', 'exception_review'))
    if (not rails.get('carrier_provenance') or not rails.get('railroad_identity')
            or not isinstance(rails.get('rail_polylines_m'), list)):
        raise ValueError('original railroad identity, carrier and all nearby rails required')
    if (not ego.get('ego_actor_id') or not ego.get('route_xy_m')
            or not ego.get('parking_footprint_xy_m') or ego.get('vehicle_action') != 'park'):
        raise ValueError('original ego route, parking footprint and action required')
    if (not other.get('vehicle_actor_id') or other['vehicle_actor_id'] == ego['ego_actor_id']
            or not other.get('route_xy_m') or not other.get('motion_plan')):
        raise ValueError('distinct other vehicle route and motion required')
    if (not isinstance(context, dict) or any(context.get(k) not in ('present', 'absent', 'unresolved') for k in EXCEPTIONS)
            or not context.get('source_review')):
        raise ValueError('four independent statutory exception reviews required')
    distance = nearest_distance(ego['parking_footprint_xy_m'], rails['rail_polylines_m'])
    if not math.isclose(distance, target_m, rel_tol=0, abs_tol=.25):
        raise ValueError('reviewed original planned parking distance differs from selected case')
    cameras = loaded['cameras']
    if not isinstance(cameras, dict) or set(cameras) != CAMERAS:
        raise ValueError('four reviewed original camera poses required')
    for pose in cameras.values():
        if (not isinstance(pose, dict) or len(pose.get('location_xyz_m', [])) != 3
                or len(pose.get('pitch_yaw_roll_deg', [])) != 3):
            raise ValueError('reviewed original camera pose invalid')
    return {'review': review, 'packet_sha256': sha(packet), 'sources': loaded,
            'source_root': str(source_root), 'planned_nearest_rail_distance_m': distance}
