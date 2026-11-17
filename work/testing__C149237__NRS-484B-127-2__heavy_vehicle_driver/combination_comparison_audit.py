"""Independent saved-source comparison of the single-truck and combination cases."""
import hashlib
import json
import math
from pathlib import Path

CASE_SUFFIXES = ('gap_at_500ft', 'combination_at_500ft')
TARGET_GAP_M = 152.4


def _read(path):
    return json.loads(path.read_text())


def _rows(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError('Missing original truck history')
    return rows


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _body(actor, tangent, combination):
    vertices = actor['body_vertices_xy_m']
    if combination:
        parts = actor.get('components', {})
        if set(parts) != {'tractor', 'trailer'}:
            raise ValueError('Missing original combination components')
        if parts['tractor']['actor_id'] == parts['trailer']['actor_id']:
            raise ValueError('Combination component identities overlap')
        merged = parts['tractor']['body_vertices_xy_m'] + parts['trailer']['body_vertices_xy_m']
        if vertices != merged:
            raise ValueError('Combination body differs from original components')
        if actor.get('native_attachment_verified') is not False or actor.get('legal_vehicle_class_verified') is not False:
            raise ValueError('Diagnostic combination claimed physical or legal qualification')
    elif actor.get('components'):
        raise ValueError('Single-truck control contains combination components')
    if len(vertices) < 4 or any(len(point) != 2 or not all(math.isfinite(float(v)) for v in point)
                                for point in vertices):
        raise ValueError('Missing original complete body')
    tx, ty = tangent
    along = [float(x)*tx + float(y)*ty for x, y in vertices]
    lateral = [-float(x)*ty + float(y)*tx for x, y in vertices]
    width = max(lateral) - min(lateral)
    if combination and not math.isclose(width, actor['overall_width_m'], abs_tol=1e-6):
        raise ValueError('Combined width differs from original component bodies')
    return min(along), max(along)


def inspect(source, suffix):
    source = Path(source)
    config, result, report, road = (_read(source/name) for name in
                                    ('config.json', 'result.json', 'analysis-report.json', 'road_context.json'))
    history, mapping = _rows(source/'truck_history.jsonl'), _rows(source/'video_frames.jsonl')
    case = config['selected_case_id']
    if not case.endswith('__'+suffix) or result['case_id'] != case:
        raise ValueError('Comparison case identity differs')
    if len(history) != len(mapping) or any(
            frame['carla_frame'] != row['frame'] or frame['time_s'] != row['time_s']
            or frame['video_frame'] != index for index, (row, frame) in enumerate(zip(history, mapping))):
        raise ValueError('Original frame join differs')
    if road['same_direction_lane_count'] != 1:
        raise ValueError('Combination comparison changed one-lane condition')
    tx, ty = map(float, road['lane_forward_xy'])
    length = math.hypot(tx, ty)
    if not length:
        raise ValueError('Missing sourced lane tangent')
    tangent = tx/length, ty/length
    gaps, velocities = [], []
    combination = suffix == 'combination_at_500ft'
    for row in history:
        spans = {}
        for role in ('ego', 'lead'):
            actor = row[role]
            if (actor['road_id'], actor['lane_id']) != (road['road_id'], road['lane_id']):
                raise ValueError('Comparison changed sourced road or lane')
            spans[role] = _body(actor, tangent, combination)
            velocity = actor['velocity_mps']
            if len(velocity) != 3 or not all(math.isfinite(float(v)) for v in velocity):
                raise ValueError('Missing original velocity')
            velocities.append(tuple(map(float, velocity)))
        gaps.append(spans['lead'][0]-spans['ego'][1])
    minimum = min(gaps)
    measurement = report['measurements']['minimum_sampled_body_gap_m']
    if not math.isclose(minimum, measurement['value'], abs_tol=1e-6):
        raise ValueError('Finalizer gap differs from original complete bodies')
    check = result['target_checks'][0]
    if not math.isclose(check['requested'], TARGET_GAP_M, abs_tol=1e-9) or not math.isclose(
            check['measured'], minimum, abs_tol=1e-6):
        raise ValueError('Reported target differs from original body gap')
    sources = {}
    for name in ('truck_history.jsonl', 'road_context.json', 'video_frames.jsonl'):
        sources[name] = _sha(source/name)
        if measurement['sources'][name] != sources[name]:
            raise ValueError('Measurement source digest differs: '+name)
    return {'case_id': case, 'gap_m': minimum, 'road_id': road['road_id'],
            'lane_id': road['lane_id'], 'lane_count': road['same_direction_lane_count'],
            'rate_hz': config['rate_hz'], 'duration_s': config['duration_s'],
            'cameras': config['cameras'], 'required_atoms': config['required_atoms'],
            'velocities': sorted(set(velocities)), 'source_sha256': sources,
            'composition': 'tractor_plus_trailer' if combination else 'single_truck'}


def audit(paths):
    if set(paths) != set(CASE_SUFFIXES):
        raise ValueError('Supply exactly the single and combination 500-foot cases')
    single, combination = (inspect(paths[suffix], suffix) for suffix in CASE_SUFFIXES)
    fixed = ('road_id', 'lane_id', 'lane_count', 'rate_hz', 'duration_s',
             'cameras', 'required_atoms', 'velocities')
    for name in fixed:
        if single[name] != combination[name]:
            raise ValueError('Fixed combination comparison condition differs: '+name)
    if any(abs(row['gap_m']-TARGET_GAP_M) > .05 for row in (single, combination)):
        raise ValueError('500-foot body-gap condition differs')
    if single['composition'] == combination['composition']:
        raise ValueError('Composition alternative was not constructed')
    return {'format':'worker-combination-comparison-audit', 'passed':True,
            'comparison_id':'truck_follow_combination_at_500ft_vs_single',
            'case_ids':[single['case_id'], combination['case_id']],
            'measured_gaps_m':[single['gap_m'], combination['gap_m']],
            'fixed_conditions':list(fixed)+['152.4 m requested complete-body gap'],
            'deliberate_difference':'single trucks versus tractor plus attached trailer',
            'source_sha256':{suffix:row['source_sha256'] for suffix,row in zip(CASE_SUFFIXES,(single,combination))},
            'scope':'synthetic saved-source software audit; Native attachment, vehicle class and legal status unresolved'}
