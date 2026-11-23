"""Source-bound geometric measurements for NRS 484B.400(2)(b).

This computes departure footprint position; it never decides legal compliance.
The packet is original map/trace data copied verbatim by a saved finalizer, not
an authored target or a vehicle center-point proxy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


def _finite_pair(value, name):
    if not isinstance(value, list) or len(value) != 2 or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in value):
        raise ValueError(f'{name} needs two finite coordinates')
    return float(value[0]), float(value[1])


def _source(path, expected, name):
    p = Path(path)
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
        raise ValueError(f'{name} missing or source hash differs')
    return json.loads(p.read_text())


def measure(map_packet, trace_packet, *, case_id):
    """Return signed full-body ranges in metres for each original departure sample.

    Positive signed coordinates lie on the geometric right of the recorded
    destination direction. No epsilon or reference point is a legal cutoff.
    """
    map_cases = map_packet.get('case_ids', [map_packet.get('case_id')])
    if case_id not in map_cases or trace_packet.get('case_id') != case_id:
        raise ValueError('case identity differs')
    if map_packet.get('road_kind') != 'two_directional_intersection' or map_packet.get('approach_two_directional') is not True or map_packet.get('destination_two_directional') is not True:
        raise ValueError('both intersecting highway directions need source evidence')
    if map_packet.get('approach_highway_status') != 'source_verified' or map_packet.get('destination_highway_status') != 'source_verified':
        raise ValueError('highway status needs source evidence')
    if map_packet.get('centerline_kind') not in ('mapped', 'source_derived_imaginary'):
        raise ValueError('centerline kind unsupported')
    if not map_packet.get('centerline_source') or not map_packet.get('direction_source'):
        raise ValueError('centerline and direction source references required')
    if trace_packet.get('approach_road_id') != map_packet.get('approach_road_id') or trace_packet.get('destination_road_id') != map_packet.get('destination_road_id'):
        raise ValueError('road connection differs')
    if trace_packet.get('maneuver') != 'left_turn' or trace_packet.get('driver_control') is not True:
        raise ValueError('left turn and driver control need trace evidence')
    origin = _finite_pair(map_packet.get('centerline_origin_xy_m'), 'centerline origin')
    direction = _finite_pair(map_packet.get('destination_direction_xy'), 'destination direction')
    norm = math.hypot(*direction)
    if norm < 0.5:
        raise ValueError('destination direction degenerate')
    direction = (direction[0] / norm, direction[1] / norm)
    right = (direction[1], -direction[0])
    samples = trace_packet.get('samples')
    if not isinstance(samples, list) or not samples:
        raise ValueError('original trace samples missing')
    result = []
    previous = -1
    found_entry = found_departure = False
    for sample in samples:
        frame = sample.get('frame')
        if not isinstance(frame, int) or frame <= previous:
            raise ValueError('frames must be strictly increasing originals')
        previous = frame
        phase = sample.get('phase')
        if phase == 'intersection_entry':
            found_entry = True
        elif phase == 'departure':
            found_departure = True
            if not found_entry:
                raise ValueError('departure before intersection entry')
            if sample.get('road_id') != map_packet['destination_road_id']:
                raise ValueError('departure not on connected destination road')
            corners = sample.get('body_corners_xy_m')
            if not isinstance(corners, list) or len(corners) < 4:
                raise ValueError('full body corners missing')
            lateral = []
            for corner in corners:
                x, y = _finite_pair(corner, 'body corner')
                lateral.append((x - origin[0]) * right[0] + (y - origin[1]) * right[1])
            result.append({'frame': frame, 'full_body_right_min_m': min(lateral), 'full_body_right_max_m': max(lateral)})
        elif phase not in ('approach', 'turning'):
            raise ValueError('unknown trace phase')
    if not found_entry or not found_departure:
        raise ValueError('intersection entry and departure samples required')
    return {
        'case_id': case_id,
        'centerline_kind': map_packet['centerline_kind'],
        'approach_road_id': map_packet['approach_road_id'],
        'destination_road_id': map_packet['destination_road_id'],
        'sample_count': len(result),
        'per_frame': result,
        'observed_right_min_m': min(x['full_body_right_min_m'] for x in result),
        'observed_right_max_m': max(x['full_body_right_max_m'] for x in result),
        'statutory_position_judgment': None,
        'limitations': ['Original discrete frames do not resolve between-frame position.', 'Geometry alone does not decide statutory interpretation or compliance.'],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--map', required=True)
    parser.add_argument('--map-sha256', required=True)
    parser.add_argument('--trace', required=True)
    parser.add_argument('--trace-sha256', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    map_packet = _source(args.map, args.map_sha256, 'map packet')
    trace_packet = _source(args.trace, args.trace_sha256, 'trace packet')
    out = measure(map_packet, trace_packet, case_id=args.case)
    out['sources'] = [
        {'path': args.map, 'sha256': args.map_sha256},
        {'path': args.trace, 'sha256': args.trace_sha256},
    ]
    Path(args.output).write_text(json.dumps(out, indent=2) + '\n')


if __name__ == '__main__':
    main()
