"""Source-gated crosswalk geometry and original-frame measurements for C111610.

Engineering distances here describe geometry and ordering, never legal cutoffs.
CARLA is imported only by a later runner that supplies its own world/map objects.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


class SourceError(ValueError):
    pass


def _require(value, message):
    if not value:
        raise SourceError(message)
    return value


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _point(value):
    _require(isinstance(value, (list, tuple)) and len(value) >= 2,
             'original point missing')
    x, y = float(value[0]), float(value[1])
    _require(math.isfinite(x) and math.isfinite(y), 'nonfinite point')
    return (x, y)


def polygon_contains(point, polygon):
    """Boundary counts as inside; vertices are original map coordinates."""
    x, y = _point(point)
    vertices = [_point(v) for v in polygon]
    _require(len(vertices) >= 3, 'original polygon has fewer than three vertices')
    inside = False
    for a, b in zip(vertices, vertices[1:] + vertices[:1]):
        ax, ay = a
        bx, by = b
        cross = (x - ax) * (by - ay) - (y - ay) * (bx - ax)
        if abs(cross) <= 1e-8 and min(ax, bx)-1e-8 <= x <= max(ax, bx)+1e-8 and min(ay, by)-1e-8 <= y <= max(ay, by)+1e-8:
            return True
        if (ay > y) != (by > y):
            if x < ax + (y-ay)*(bx-ax)/(by-ay):
                inside = not inside
    return inside


def directional_half(lanes, destination_lane_ids):
    """Use all original lanes designated for destination travel, not lane center."""
    _require(lanes and destination_lane_ids, 'original lane inventory missing')
    by_id = {str(lane['lane_id']): lane for lane in lanes}
    selected = set(map(str, destination_lane_ids))
    _require(selected <= by_id.keys(), 'destination lane absent in original map')
    directions = {by_id[key].get('direction') for key in selected}
    _require(len(directions) == 1 and None not in directions,
             'destination half has inconsistent lane directions')
    direction = next(iter(directions))
    full_half = {key for key, lane in by_id.items() if lane.get('direction') == direction and lane.get('type') == 'driving'}
    _require(full_half == selected, 'destination half omits a same-direction driving lane')
    for key in selected:
        _require(len(by_id[key].get('polygon_xy_m', [])) >= 3, 'original lane polygon missing')
    return [by_id[key]['polygon_xy_m'] for key in sorted(selected)]


def bind_site(packet, expected_map, expected_turn):
    """Require a sourced intersection/crosswalk, connected turn, and device inventory."""
    _require(packet.get('source') == 'original_native_map', 'original map source missing')
    _require(packet.get('map_name') == expected_map, 'wrong original map')
    _require(packet.get('intersection_id'), 'original intersection identity missing')
    _require(packet.get('highway_context', {}).get('source') == 'original_map_and_local_review',
             'highway context source missing')
    crosswalk = packet.get('crosswalk', {})
    _require(crosswalk.get('source') in ('original_map_marking', 'original_intersection_geometry'),
             'crosswalk classification source missing')
    _require(len(crosswalk.get('polygon_xy_m', [])) >= 3, 'crosswalk geometry missing')
    route = packet.get('ego_turn', {})
    _require(route.get('direction') == expected_turn and route.get('connected') is True,
             'original connected turn missing')
    _require(len(route.get('waypoints', [])) >= 3, 'original turn waypoints missing')
    _require(route.get('destination_lane_ids'), 'destination lane identity missing')
    half = directional_half(packet.get('lanes'), route['destination_lane_ids'])
    devices = packet.get('official_devices')
    _require(isinstance(devices, dict) and devices.get('inventory_source') == 'original_map_and_actor_scan',
             'official-device inventory source missing')
    _require(devices.get('coverage') == 'all_relevant_approaches',
             'official-device inventory incomplete')
    _require(isinstance(devices.get('entries'), list), 'official-device entries missing')
    return {'crosswalk_polygon': crosswalk['polygon_xy_m'], 'destination_half': half,
            'destination_lane_ids': route['destination_lane_ids'],
            'device_entries': devices['entries'], 'turn_route': route['waypoints']}


def device_condition(entries, frame):
    """Unknown inventory/state stays unknown; an actor not found is no absence proof."""
    states = []
    for entry in entries:
        _require(entry.get('official') is True and entry.get('relevant') is True,
                 'official-device classification missing')
        _require(entry.get('source_ref'), 'official-device source reference missing')
        history = entry.get('state_by_frame')
        _require(isinstance(history, dict) and str(frame) in history,
                 'official-device original state missing')
        state = history[str(frame)]
        _require(state in ('operating', 'not_operating', 'absent'),
                 'unknown official-device state')
        states.append(state)
    return 'absent' if not states else ('operating' if 'operating' in states else 'not_operating')


def measure_frame(site, frame, ego, pedestrian, exception_review):
    """Project original body positions and order; no compliance/legal label."""
    _require(type(frame) is int and frame >= 0, 'invalid original frame')
    _require(ego.get('frame') == frame and pedestrian.get('frame') == frame,
             'original frame join mismatch')
    _require(ego.get('source_ref') and pedestrian.get('source_ref'),
             'original participant source missing')
    _require(ego.get('actor_id') != pedestrian.get('actor_id'),
             'driver and pedestrian identities overlap')
    _require(ego.get('classification') == 'motor_vehicle_driver' and
             pedestrian.get('classification') == 'pedestrian',
             'participant classification unverified')
    _require(exception_review.get('source_refs') and
             exception_review.get('status') in ('none_identified', 'possible', 'applies'),
             'introductory exception review missing')
    person = _point(pedestrian['body_center_xy_m'])
    ego_pos = _point(ego['body_center_xy_m'])
    crosswalk = polygon_contains(person, site['crosswalk_polygon'])
    destination_half = any(polygon_contains(person, lane) for lane in site['destination_half'])
    return {'frame': frame, 'pedestrian_in_crosswalk': crosswalk,
            'pedestrian_on_destination_half': destination_half,
            'pedestrian_to_ego_distance_m': math.dist(person, ego_pos),
            'ego_brake': bool(ego.get('brake')),
            'device_condition': device_condition(site['device_entries'], frame),
            'exception_review_status': exception_review['status'],
            'original_sources': [ego['source_ref'], pedestrian['source_ref'],
                                 *exception_review['source_refs']]}


def audit_comparison(left, right, fixed_keys, differing_key):
    _require(left.get('case_id') and right.get('case_id') and left['case_id'] != right['case_id'],
             'two distinct cases required')
    for key in fixed_keys:
        _require(left.get(key) is not None and right.get(key) is not None,
                 'missing fixed comparison source: ' + key)
        _require(left[key] == right[key], 'fixed comparison changed: ' + key)
    _require(left.get(differing_key) is not None and right.get(differing_key) is not None,
             'missing comparison variable source: ' + differing_key)
    _require(left[differing_key] != right[differing_key],
             'declared comparison variable did not differ')
    return {'status': 'source_compared', 'case_ids': [left['case_id'], right['case_id']],
            'fixed_keys': fixed_keys, 'differing_key': differing_key}
