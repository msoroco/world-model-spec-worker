"""Independent source comparison for the three road-configuration alternatives."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from right_half_measurement import measure

PREFIX = 'heldout__C230259__NRS-484B-200-1__motor_vehicle_driver__'
TARGETS = {
    'three_lane_left': ('three_lane_setup', 'three_lane_exception'),
    'one_way_left': ('one_way_setup', 'one_way_exception'),
    'narrow_left': ('narrow_setup', 'width_exception'),
}


def source(root, name):
    path = Path(root) / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing original comparison source: ' + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def audit(baseline_root, target_root, suffix):
    if suffix not in TARGETS:
        raise ValueError('Unknown road-configuration comparison')
    baseline, target = Path(baseline_root), Path(target_root)
    if baseline.resolve() == target.resolve():
        raise ValueError('Comparison repeats one attempt')
    setup_key, comparison_id = TARGETS[suffix]
    for root, name in ((baseline, 'baseline_left'), (target, suffix)):
        config = json.loads(source(root, 'config.json').read_text())
        if config.get('selected_case_id') != PREFIX + name or (config.get('rate_hz'), config.get('frames'), config.get('duration_s')) != (20, 80, 4):
            raise ValueError('Comparison exact case or capture duration differs')
        if [camera.get('name') for camera in config.get('cameras', [])] != ['overview', 'approach', 'reference_corner', 'driver_reference']:
            raise ValueError('Comparison four-camera contract differs')
    names = ('ego_road_frames.jsonl', 'road_exception_context.json', 'video_frames.jsonl', 'trace.jsonl')
    base_sources = {name: source(baseline, name) for name in names}
    target_sources = {name: source(target, name) for name in names}
    bodies = [rows(base_sources[names[0]]), rows(target_sources[names[0]])]
    maps = [rows(base_sources[names[2]]), rows(target_sources[names[2]])]
    traces = [rows(base_sources[names[3]]), rows(target_sources[names[3]])]
    if len(bodies[0]) < 3 or any(len(part) != len(bodies[0]) for part in bodies + maps + traces):
        raise ValueError('Comparison original source frame counts differ')
    fixed = ('frame', 'time_s', 'road_id', 'road_center_xy', 'road_travel_tangent_xy')
    for base, changed, base_map, changed_map, base_trace, changed_trace in zip(*bodies, *maps, *traces):
        if any(base.get(key) != changed.get(key) for key in fixed):
            raise ValueError('Comparison road alignment or timing changed')
        if base_map != changed_map or (base_trace['frame'], base_trace['time_s']) != (changed_trace['frame'], changed_trace['time_s']):
            raise ValueError('Comparison frame map or trace timing changed')
    base_context = json.loads(base_sources[names[1]].read_text())
    changed_context = json.loads(target_sources[names[1]].read_text())
    setup = changed_context.pop(setup_key, None)
    if base_context != changed_context or not isinstance(setup, dict) or setup.get('subject_path') != 'left_half':
        raise ValueError('Comparison changed unrelated exception context')
    for paths in (base_sources, target_sources):
        result = measure(paths[names[0]], paths[names[1]])
        if not all(row['whole_body_left_half'] for row in result['observations']):
            raise ValueError('Comparison body did not remain wholly left')
    source_hashes = {name: sha(path) for name, path in target_sources.items()}
    if suffix == 'three_lane_left':
        if setup.get('applicable_lane_rule') != 'undecided' or len(setup.get('lane_ids', [])) != 3:
            raise ValueError('Three-lane rule/setup source changed')
        if not all(len(row.get('lane_inventory', [])) == 3 and row['road_width_m'] > base['road_width_m'] for base, row in zip(*bodies)):
            raise ValueError('Three-lane source does not establish changed lane inventory and width')
    elif suffix == 'one_way_left':
        if setup.get('official_designation') != 'undecided' or setup.get('posting_authority') != 'undecided' or not setup.get('sign_actor_id'):
            raise ValueError('One-way official status or sign source changed')
        if not all(len(row.get('lane_inventory', [])) == 2 and row['road_width_m'] == base['road_width_m'] for base, row in zip(*bodies)):
            raise ValueError('One-way lane inventory or fixed width changed')
        sign = rows(source(target, 'one_way_sign.jsonl'))
        if len(sign) != len(bodies[1]) or any((s['frame'], s['time_s']) != (r['frame'], r['time_s']) for s, r in zip(sign, bodies[1])):
            raise ValueError('One-way sign original frame join changed')
        source_hashes['one_way_sign.jsonl'] = sha(source(target, 'one_way_sign.jsonl'))
    else:
        if setup.get('legal_sufficiency') != 'undecided' or setup.get('candidate_max_road_width_m') != 6.5:
            raise ValueError('Narrow-road legal/engineering screen changed')
        if not all(row['road_width_m'] <= 6.5 and row['road_width_m'] < base['road_width_m'] for base, row in zip(*bodies)):
            raise ValueError('Narrow-road width contrast is absent')
    return {'format': 'worker-right-half-road-comparison', 'comparison_id': comparison_id,
            'baseline_case_id': PREFIX + 'baseline_left', 'target_case_id': PREFIX + suffix,
            'frames': len(bodies[0]), 'fixed_original_keys': list(fixed) + ['video frame map', 'trace timing', 'unrelated exception context'],
            'changed_source_sha256': source_hashes, 'passed': True,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--suffix', choices=sorted(TARGETS), required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.baseline, args.target, args.suffix)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'comparison_id': result['comparison_id'], 'frames': result['frames'], 'passed': True}))
