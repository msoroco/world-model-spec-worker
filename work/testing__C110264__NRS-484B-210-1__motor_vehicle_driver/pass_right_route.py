"""Map-gated route requests for a right pass near an intersection.

The returned coordinates are CARLA-lazy requests. Native map geometry and actor
poses must be remeasured in the same live attempt before execution is accepted.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def load_map_packet(path: Path, expected_sha256: str) -> dict:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('map packet sha256 mismatch')
    packet = json.loads(raw)
    if packet.get('source_kind') != 'original_native_map_geometry':
        raise ValueError('original Native map geometry required')
    return packet


def build_case(packet: dict, variant: str) -> dict:
    if variant not in ('left_signal', 'left_turn', 'neither'):
        raise ValueError('unknown exact variant')
    if packet.get('source_kind') != 'original_native_map_geometry':
        raise ValueError('original Native map geometry required')
    if packet.get('direction') != 'two_way' or packet.get('same_direction_marked_lanes') != 1:
        raise ValueError('exact intersection cell road direction/lane count mismatch')
    interval = packet.get('intersection_s_m')
    if (not isinstance(interval, list) or len(interval) != 2 or
            not all(isinstance(v, (int, float)) and math.isfinite(v) for v in interval) or
            interval[0] >= interval[1]):
        raise ValueError('source-confirmed intersection interval required')
    samples = packet.get('cross_sections', [])
    stations = [s.get('station_m') for s in samples]
    if (len(samples) < 3 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in stations) or
            stations != sorted(set(stations)) or max(b - a for a, b in zip(stations, stations[1:])) > 5.0 or
            stations[0] > interval[0] - 10.0 or stations[-1] < interval[1] + 10.0):
        raise ValueError('route cross sections do not cover intersection and approaches')
    half_width = packet.get('actor_half_width_m')
    if not isinstance(half_width, (int, float)) or half_width <= 0 or not math.isfinite(half_width):
        raise ValueError('source actor footprint missing')
    ego_y = packet.get('right_pass_center_m')
    target_y = packet.get('target_lane_center_m')
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (ego_y, target_y)):
        raise ValueError('source lane and pass centers required')
    if ego_y - target_y < 2 * half_width + 0.5:
        raise ValueError('right pass centers do not clear actor footprints')
    for s in samples:
        if s.get('source') != 'native_map' or s.get('right_positive') is not True:
            raise ValueError('cross section lacks native provenance or orientation')
        left, right = s['paved_lateral_bounds_m']
        if not (left + half_width <= target_y <= right - half_width and
                left + half_width <= ego_y <= right - half_width):
            raise ValueError('actor footprint exceeds paved corridor')
        if right - ego_y - half_width < 0.25:
            raise ValueError('insufficient right pavement margin')
    # The target turn is a distinct route request; no turn is inferred from signal.
    if not isinstance(packet.get('turn_lateral_displacement_m'), (int, float)) or packet['turn_lateral_displacement_m'] <= 0:
        raise ValueError('source-compatible target turn displacement required')
    target_path = [[s['station_m'], target_y - packet['turn_lateral_displacement_m'] if variant == 'left_turn' and s['station_m'] >= interval[1] else target_y]
                   for s in samples]
    return {
        'variant': variant, 'coordinate_frame': 'source_station_right_positive',
        'ego_path_s_lateral_m': [[s['station_m'], ego_y] for s in samples],
        'target_path_s_lateral_m': target_path,
        'target_left_signal_request': variant == 'left_signal',
        'target_turn_request': variant == 'left_turn',
        'actor_half_width_m': half_width,
        'intersection_s_m': interval,
        'native_recheck_required': True,
        'other_permission_alternatives': 'unresolved',
    }
