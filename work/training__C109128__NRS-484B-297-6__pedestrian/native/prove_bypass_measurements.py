"""Derive bypass observations from retained synthetic position and footprint rows.

These measurements exercise the CPU finalization design. They do not establish
that a sidewalk was obstructed in Native, that a return was practicable, or that
the pedestrian exercised due care.
"""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
CONTEXT = HERE / 'diagnostic-bypass/context.json'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def derive(path, context_path=CONTEXT):
    path = Path(path)
    context = json.loads(Path(context_path).read_text())
    if (context.get('context_id') != 'c109128-sidewalk-obstruction-v1' or
            context.get('roadway_y_range_m') != [0.0, 2.0] or
            context.get('obstruction_x_range_m') != [20.0, 30.0] or
            context.get('obstruction_y_range_m') != [2.0, 4.0] or
            context.get('physical_obstruction_verified') is not False):
        raise ValueError('Untrusted bypass context')
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if len(rows) != 600:
        raise ValueError('Expected 600 source frames')
    measured = []
    prior = None
    total_m = 0.0
    for frame, row in enumerate(rows):
        center = row['pedestrian_xy_m']
        feet = row['footprint_xy_m']
        if (row['frame'] != frame or row['time_s'] != frame / 20 or
                row['context_id'] != context['context_id'] or
                row['source_kind'] != 'synthetic_scene_request' or
                row['original_native_observed'] is not False or
                row['legal_verdict'] is not None or
                len(center) != 2 or len(feet) != 4 or
                any(len(point) != 2 for point in feet)):
            raise ValueError('Invalid bypass source row')
        values = [*center, *(value for point in feet for value in point)]
        if any(type(value) not in (int, float) or not math.isfinite(value) for value in values):
            raise ValueError('Nonfinite bypass geometry')
        if (min(point[0] for point in feet) > center[0] or
                max(point[0] for point in feet) < center[0] or
                min(point[1] for point in feet) > center[1] or
                max(point[1] for point in feet) < center[1]):
            raise ValueError('Pedestrian center outside footprint')
        dx = dy = 0.0
        if prior is not None:
            dx, dy = center[0] - prior[0], center[1] - prior[1]
            step = math.hypot(dx, dy)
            if step > 0.12:
                raise ValueError('Pedestrian frame discontinuity')
            total_m += step
        prior = center
        min_y = min(point[1] for point in feet)
        max_y = max(point[1] for point in feet)
        measured.append({
            'frame': frame, 'time_s': frame / 20,
            'center_roadway': 0 <= center[1] < 2,
            'footprint_overlaps_roadway': min_y < 2 and max_y >= 0,
            'footprint_on_sidewalk': min_y >= 2,
            'center_distance_to_road_edge_m': round(abs(2 - center[1]), 6),
            'longitudinal_direction': 'forward' if dx > 0 else ('reverse' if dx < 0 else 'stationary'),
            'path_length_m': round(total_m, 6),
            'past_obstruction': center[0] - 0.16 > 30,
        })
    first_road = next((r['frame'] for r in measured if r['footprint_overlaps_roadway']), None)
    last_road = next((r['frame'] for r in reversed(measured) if r['footprint_overlaps_roadway']), None)
    first_clear = next((r['frame'] for r in measured if r['past_obstruction']), None)
    first_return = next((r['frame'] for r in measured if
                         r['past_obstruction'] and r['footprint_on_sidewalk']), None)
    if None in (first_road, last_road, first_clear, first_return) or not first_road < first_clear <= first_return:
        raise ValueError('Missing complete sidewalk bypass and return')
    if any(r['longitudinal_direction'] == 'reverse' for r in measured[1:]):
        raise ValueError('Bypass reverses sidewalk travel direction')
    road = [r for r in measured if r['center_roadway']]
    return {
        'format': 'c109128-source-derived-bypass-measurement-v1',
        'source_sha256': digest(path), 'context_sha256': digest(context_path),
        'frames': len(rows), 'rate_hz': 20, 'duration_s': 30,
        'first_road_footprint_frame': first_road,
        'last_road_footprint_frame': last_road,
        'first_unobstructed_sidewalk_geometry_frame': first_clear,
        'first_full_footprint_return_frame': first_return,
        'geometry_return_lag_frames': first_return - first_clear,
        'road_center_frames': len(road),
        'minimum_road_center_distance_to_edge_m': min(r['center_distance_to_road_edge_m'] for r in road),
        'maximum_road_center_distance_to_edge_m': max(r['center_distance_to_road_edge_m'] for r in road),
        'total_path_length_m': measured[-1]['path_length_m'],
        'original_native_observed': False,
        'physical_obstruction_verified': False,
        'first_practicable_return_verified': False,
        'due_care_verified': False,
        'legal_verdict_claimed': False,
    }


def main():
    a = derive(HERE / 'diagnostic-bypass/condition_a.jsonl')
    b = derive(HERE / 'diagnostic-bypass/condition_b.jsonl')
    if not a['minimum_road_center_distance_to_edge_m'] < b['minimum_road_center_distance_to_edge_m']:
        raise ValueError('Bypass lateral contrast absent')
    if a['first_unobstructed_sidewalk_geometry_frame'] != b['first_unobstructed_sidewalk_geometry_frame']:
        raise ValueError('Obstruction geometry differs between conditions')
    proof = {'format': 'c109128-measurement-proof-v1', 'passed': True,
             'condition_a': a, 'condition_b': b,
             'comparison_variable': 'pedestrian_bypass_path',
             'fixed_longitudinal_motion_and_obstruction': True,
             'physical_success_claimed': False, 'legal_verdict_claimed': False}
    target = HERE / 'bypass-measurement-proof.json'
    target.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'passed': True, 'proof_sha256': digest(target),
                      'return_frames': [a['first_full_footprint_return_frame'],
                                        b['first_full_footprint_return_frame']]}))


if __name__ == '__main__':
    main()
