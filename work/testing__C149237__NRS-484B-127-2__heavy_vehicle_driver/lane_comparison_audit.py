"""Compare the one- and two-lane exception controls from retained sources."""
import argparse
import hashlib
import json
import math
from pathlib import Path

CASES = ('gap_below_500ft', 'two_same_direction_lanes')


def inspect(path, suffix):
    root = Path(path)
    config = json.loads((root/'config.json').read_text())
    result = json.loads((root/'result.json').read_text())
    report = json.loads((root/'analysis-report.json').read_text())
    road = json.loads((root/'road_context.json').read_text())
    history = [json.loads(s) for s in (root/'truck_history.jsonl').read_text().splitlines() if s]
    frames = [json.loads(s) for s in (root/'video_frames.jsonl').read_text().splitlines() if s]
    if not config['selected_case_id'].endswith('__'+suffix) or result['case_id'] != config['selected_case_id']:
        raise ValueError('Lane comparison case identity differs')
    if not history or len(history) != len(frames) or any(
            h['frame'] != f['carla_frame'] or h['time_s'] != f['time_s'] or f['video_frame'] != i
            for i, (h, f) in enumerate(zip(history, frames))):
        raise ValueError('Lane comparison original frame join differs')
    count = road['same_direction_lane_count']
    expected = 1 if suffix == CASES[0] else 2
    if count != expected:
        raise ValueError('Lane comparison source lane count differs from target')
    tx, ty = road['lane_forward_xy']
    norm = math.hypot(tx, ty)
    if norm <= 0:
        raise ValueError('Missing lane tangent')
    tx, ty = tx/norm, ty/norm
    gaps = []
    for h in history:
        projections = {}
        for role in ('ego', 'lead'):
            actor = h[role]
            if (not actor.get('is_truck_or_combination') or
                    actor['road_id'] != road['road_id'] or actor['lane_id'] != road['lane_id'] or
                    len(actor['body_vertices_xy_m']) < 4):
                raise ValueError('Lane comparison lost same-lane truck relation')
            projections[role] = [x*tx+y*ty for x, y in actor['body_vertices_xy_m']]
        gaps.append(min(projections['lead'])-max(projections['ego']))
    gap = min(gaps)
    if not math.isclose(gap, report['measurements']['minimum_sampled_body_gap_m']['value'], abs_tol=1e-6):
        raise ValueError('Lane comparison finalizer gap differs from original source')
    for name in ('truck_history.jsonl', 'road_context.json', 'video_frames.jsonl'):
        source_hash = hashlib.sha256((root/name).read_bytes()).hexdigest()
        if report['measurements']['minimum_sampled_body_gap_m']['sources'][name] != source_hash:
            raise ValueError('Lane comparison source hash differs: '+name)
    widths = {role: min(float(h[role]['overall_width_m']) for h in history) for role in ('ego', 'lead')}
    blueprints = {role: sorted({h[role]['blueprint_id'] for h in history}) for role in ('ego', 'lead')}
    if any(len(ids) != 1 for ids in blueprints.values()):
        raise ValueError('Truck identity changed within case')
    return {'case_id': result['case_id'], 'lane_count': count, 'gap_m': gap,
            'widths_m': widths, 'blueprints': blueprints,
            'rate_hz': config['rate_hz'], 'duration_s': config['duration_s'],
            'cameras': config['cameras'], 'required_atoms': config['required_atoms']}


def audit(paths):
    if set(paths) != set(CASES):
        raise ValueError('Supply exact one- and two-lane cases')
    one, two = (inspect(paths[s], s) for s in CASES)
    for key in ('widths_m', 'blueprints', 'rate_hz', 'duration_s', 'cameras', 'required_atoms'):
        if one[key] != two[key]:
            raise ValueError('Lane comparison changed fixed condition: '+key)
    if abs(one['gap_m']-150) > .05 or abs(two['gap_m']-150) > .05:
        raise ValueError('Lane comparison changed fixed body gap')
    return {'format': 'worker-lane-exception-comparison-audit', 'passed': True,
            'comparison_id': 'two_lanes_exception',
            'case_ids': [one['case_id'], two['case_id']],
            'measured_lane_counts': [one['lane_count'], two['lane_count']],
            'measured_gaps_m': [one['gap_m'], two['gap_m']],
            'scope': 'synthetic saved-source software audit; physical and legal status unresolved'}


def main():
    parser = argparse.ArgumentParser()
    for suffix in CASES:
        parser.add_argument('--'+suffix.replace('_', '-'), required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior lane comparison receipt')
    output.write_text(json.dumps(audit({s: getattr(args, s) for s in CASES}), indent=2)+'\n')


if __name__ == '__main__':
    main()
