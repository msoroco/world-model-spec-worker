"""Independent source-bound comparison for four physical Walk margin probes."""
import argparse
import hashlib
import json
from pathlib import Path

from sweep_delivery_audit import HERE, audit as audit_delivery, require

SUFFIXES = tuple(f'right_of_way_physical_context-{n:04d}' for n in range(4))


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fixed_config(config):
    result = dict(config)
    for key in ('case_id', 'case_suffix', 'selected_case_id', 'supported_case_ids', 'case'):
        result.pop(key, None)
    result['knobs'] = dict(result['knobs'])
    result['knobs'].pop('crosswalk_hold_margin_m', None)
    return result


def compare(attempts, processing, *, diagnostic=False, manifest_path=None):
    require(set(attempts) == set(SUFFIXES) and set(processing) == set(SUFFIXES),
            'Sweep comparison needs four exact cases')
    reviewed = {}
    for suffix in SUFFIXES:
        case = HERE.name + '__' + suffix
        reviewed[suffix] = audit_delivery(case, 'primary', attempts[suffix],
                                          processing[suffix], diagnostic=diagnostic,
                                          manifest_path=manifest_path)
    configs = {key: read(Path(attempts[key]) / 'config.json') for key in SUFFIXES}
    setpoints = {key: configs[key]['knobs']['crosswalk_hold_margin_m'] for key in SUFFIXES}
    require(set(setpoints.values()) == {0.5, 1.0, 1.5, 2.0},
            'Sweep controller setpoints differ from the fixed four-point grid')
    fixed = [fixed_config(configs[key]) for key in SUFFIXES]
    require(all(item == fixed[0] for item in fixed[1:]),
            'Sweep construction changed a fixed setting')
    roads = [read(Path(attempts[key]) / 'road_geometry.json') for key in SUFFIXES]
    for key in ('cell_id', 'native_map_sha256', 'crosswalk_y_range_m',
                'bus_lane_x_range_m', 'authored_walk_signal_id'):
        require(all(item.get(key) == roads[0].get(key) for item in roads[1:]),
                'Sweep road or signal geometry differs: ' + key)
    samples = {key: rows(Path(attempts[key]) / 'native_samples.jsonl') for key in SUFFIXES}
    maps = {key: rows(Path(attempts[key]) / 'video_frames.jsonl') for key in SUFFIXES}
    require(all(len(samples[key]) == len(maps[key]) == 480 for key in SUFFIXES),
            'Sweep source frame count differs')
    first = SUFFIXES[0]
    for index in range(480):
        original = samples[first][index]
        original_map = maps[first][index]
        for key in SUFFIXES[1:]:
            row, mapped = samples[key][index], maps[key][index]
            require(row.get('pedestrian_body_xy_m') == original.get('pedestrian_body_xy_m')
                    and row.get('walk_display_request') == original.get('walk_display_request')
                    and row.get('speed_provenance') == original.get('speed_provenance')
                    and mapped.get('video_frame') == original_map.get('video_frame') == index
                    and abs(mapped['time_s'] - original_map['time_s']) <= 0.05,
                    'Sweep fixed pedestrian, Walk request or frame time differs')
    observed = {}
    for key in SUFFIXES:
        receipt = read(processing[key])
        result = read(receipt['result'])
        observed[key] = result['realized_observables']['crosswalk_hold_margin_m']['value']
    if not diagnostic:
        require(all(reviewed[key]['passed'] for key in SUFFIXES),
                'Original sweep delivery review incomplete')
        require(len(set(observed.values())) >= 2,
                'Original sweep did not realize distinct measured margins')
    return {'format': 'c111256-independent-physical-sweep-comparison-v1',
            'comparison_id': HERE.name + '__right_of_way_physical_context_sweep',
            'case_ids': [HERE.name + '__' + key for key in SUFFIXES],
            'passed': not diagnostic, 'diagnostic_source_shape_passed': True,
            'setpoint_margin_m': setpoints, 'observed_margin_m': observed,
            'source_sha256': {key: sha(Path(attempts[key]) / 'native_samples.jsonl')
                              for key in SUFFIXES},
            'fixed_conditions_checked': ['construction except requested margin',
                                          'road and Walk signal geometry',
                                          'pedestrian body', 'Walk request', 'frame time'],
            'original_physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--attempt-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    require(not args.output.exists(), 'Retain prior comparison audit output')
    attempts = {key: args.attempt_root / key / 'attempt' for key in SUFFIXES}
    processing = {key: args.attempt_root / key / 'processed/v0001/processing.json'
                  for key in SUFFIXES}
    result = compare(attempts, processing, diagnostic=args.diagnostic,
                     manifest_path=args.manifest)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'comparison_id': result['comparison_id'],
                      'passed': result['passed'], 'diagnostic': args.diagnostic}))


if __name__ == '__main__':
    main()
