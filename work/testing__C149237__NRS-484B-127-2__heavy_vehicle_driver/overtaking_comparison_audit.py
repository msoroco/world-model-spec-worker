"""Independent saved-source comparison of following and overtaking controls."""
import argparse
import hashlib
import json
import math
from pathlib import Path

CASES = ('gap_below_500ft', 'overtaking')
EXPECTED = ('following_behind', 'passing_behind', 'passing_ahead', 'returned_ahead')


def inspect(path, suffix):
    root = Path(path)
    config = json.loads((root/'config.json').read_text())
    result = json.loads((root/'result.json').read_text())
    report = json.loads((root/'analysis-report.json').read_text())
    road = json.loads((root/'road_context.json').read_text())
    history = [json.loads(s) for s in (root/'truck_history.jsonl').read_text().splitlines() if s]
    frames = [json.loads(s) for s in (root/'video_frames.jsonl').read_text().splitlines() if s]
    if not config['selected_case_id'].endswith('__'+suffix) or result['case_id'] != config['selected_case_id']:
        raise ValueError('Overtaking comparison case identity differs')
    if not history or len(history) != len(frames) or any(
            h['frame'] != f['carla_frame'] or h['time_s'] != f['time_s'] or f['video_frame'] != i
            for i, (h, f) in enumerate(zip(history, frames))):
        raise ValueError('Overtaking original frame join differs')
    if road['same_direction_lane_count'] != 1:
        raise ValueError('Overtaking comparison changed one-forward-lane condition')
    if suffix == 'overtaking' and road.get('passing_lane_id') == road['lane_id']:
        raise ValueError('Passing lane is the following lane')
    tx, ty = road['lane_forward_xy']
    norm = math.hypot(tx, ty)
    if not norm:
        raise ValueError('Missing sourced lane tangent')
    tx, ty = tx/norm, ty/norm
    gaps, phases = [], []
    for h in history:
        projected = {}
        for role in ('ego', 'lead'):
            actor = h[role]
            allowed = {road['lane_id'], road.get('passing_lane_id')} if role == 'ego' and suffix == 'overtaking' else {road['lane_id']}
            if actor['road_id'] != road['road_id'] or actor['lane_id'] not in allowed or not actor.get('is_truck_or_combination'):
                raise ValueError('Overtaking comparison lost truck road/lane relation')
            vertices = actor['body_vertices_xy_m']
            if len(vertices) < 4:
                raise ValueError('Missing original truck body vertices')
            projected[role] = [x*tx+y*ty for x, y in vertices]
        gap = min(projected['lead'])-max(projected['ego'])
        gaps.append(gap)
        lane = h['ego']['lane_id']
        phases.append('following_behind' if lane == road['lane_id'] and gap > 0 else
                      'passing_behind' if lane == road.get('passing_lane_id') and gap > 0 else
                      'passing_ahead' if lane == road.get('passing_lane_id') and gap < 0 else
                      'returned_ahead' if lane == road['lane_id'] and gap < 0 else 'ambiguous')
    for name in ('truck_history.jsonl', 'road_context.json', 'video_frames.jsonl'):
        checksum = hashlib.sha256((root/name).read_bytes()).hexdigest()
        if report['measurements']['minimum_sampled_body_gap_m']['sources'][name] != checksum:
            raise ValueError('Overtaking source hash differs: '+name)
    if not math.isclose(min(gaps), report['measurements']['minimum_sampled_body_gap_m']['value'], abs_tol=1e-6):
        raise ValueError('Overtaking finalizer gap differs from original bodies')
    if suffix == 'overtaking' and report['measurements']['overtaking_phase_sequence']['value'] != phases:
        raise ValueError('Overtaking finalizer phases differ from original lanes/bodies')
    return {'case_id': result['case_id'], 'initial_gap_m': gaps[0], 'gaps_m': gaps,
            'phases': phases, 'widths_m': {role: min(h[role]['overall_width_m'] for h in history)
                                           for role in ('ego', 'lead')},
            'blueprints': {role: sorted({h[role]['blueprint_id'] for h in history})
                           for role in ('ego', 'lead')},
            'lane_count': road['same_direction_lane_count'], 'cameras': config['cameras'],
            'rate_hz': config['rate_hz'], 'duration_s': config['duration_s'],
            'required_atoms': config['required_atoms']}


def audit(paths):
    if set(paths) != set(CASES):
        raise ValueError('Supply exact following and overtaking cases')
    base, passing = (inspect(paths[s], s) for s in CASES)
    for key in ('widths_m', 'blueprints', 'lane_count', 'cameras', 'rate_hz', 'duration_s', 'required_atoms'):
        if base[key] != passing[key]:
            raise ValueError('Overtaking changed fixed condition: '+key)
    if abs(base['initial_gap_m']-150) > .05 or abs(passing['initial_gap_m']-150) > .05:
        raise ValueError('Overtaking changed fixed initial body gap')
    if any(phase != 'following_behind' for phase in base['phases']):
        raise ValueError('Following control is not a stable behind relation')
    cursor = 0
    for phase in EXPECTED:
        while cursor < len(passing['phases']) and passing['phases'][cursor] != phase:
            cursor += 1
        if cursor == len(passing['phases']):
            raise ValueError('Passing sequence omits '+phase)
        cursor += 1
    return {'format': 'worker-overtaking-comparison-audit', 'passed': True,
            'comparison_id': 'overtaking_exception',
            'case_ids': [base['case_id'], passing['case_id']],
            'initial_gaps_m': [base['initial_gap_m'], passing['initial_gap_m']],
            'passing_phases': passing['phases'],
            'scope': 'synthetic saved-source software audit; traffic safety and legal/physical status unresolved'}


def main():
    parser = argparse.ArgumentParser()
    for suffix in CASES:
        parser.add_argument('--'+suffix.replace('_', '-'), required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain previous overtaking comparison receipt')
    output.write_text(json.dumps(audit({s: getattr(args, s) for s in CASES}), indent=2)+'\n')


if __name__ == '__main__':
    main()
