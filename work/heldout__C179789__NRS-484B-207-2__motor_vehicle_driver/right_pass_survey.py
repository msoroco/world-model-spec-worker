"""Collect original Native map facts for later right-pass premise review.

No road geometry or absence of obstruction is inferred from this helper.
"""
from __future__ import annotations
from math import isfinite


def collect(map_name, waypoint, frame, time_s, observed_vehicle_ids):
    if not isinstance(map_name, str) or not map_name.strip():
        raise ValueError('Original map identity missing')
    if type(frame) is not int or frame < 0 or type(time_s) not in (int, float) or not isfinite(time_s):
        raise ValueError('Original survey frame or time invalid')
    if waypoint is None or getattr(waypoint, 'is_junction', None) is None:
        raise ValueError('Original road waypoint missing')
    road_id = getattr(waypoint, 'road_id', None)
    lane_id = getattr(waypoint, 'lane_id', None)
    width = getattr(waypoint, 'lane_width', None)
    if type(road_id) is not int or type(lane_id) is not int or type(width) not in (int, float) or not isfinite(width) or width <= 0:
        raise ValueError('Original road and lane geometry invalid')
    neighbor = waypoint.get_right_lane() if callable(getattr(waypoint, 'get_right_lane', None)) else None
    right_lane_id = getattr(neighbor, 'lane_id', None)
    right_road_id = getattr(neighbor, 'road_id', None)
    if neighbor is not None and (type(right_lane_id) is not int or type(right_road_id) is not int):
        raise ValueError('Original right-side lane identity invalid')
    if not isinstance(observed_vehicle_ids, list) or any(type(x) is not int or x < 0 for x in observed_vehicle_ids):
        raise ValueError('Original observed-vehicle inventory invalid')
    return {
        'format': 'worker-original-right-pass-road-survey-readback',
        'source_kind': 'original_road_survey',
        'map_name': map_name, 'road_id': road_id, 'lane_ids': [lane_id] + ([right_lane_id] if neighbor is not None else []),
        'right_neighbor_road_id': right_road_id, 'subject_lane_width_m': float(width),
        'is_junction': bool(waypoint.is_junction), 'frame': frame, 'time_s': float(time_s),
        'observed_vehicle_ids': observed_vehicle_ids,
        'passing_side': 'right', 'source_provenance': 'Native map waypoint readback at original frame',
        'pavement_unobstructed': None, 'parked_vehicle_free': None,
        'one_way_restriction': None, 'left_turn_signal_observed': None,
        'safety_condition_verified': None, 'permission_state': None, 'legal_conclusion': None,
    }
