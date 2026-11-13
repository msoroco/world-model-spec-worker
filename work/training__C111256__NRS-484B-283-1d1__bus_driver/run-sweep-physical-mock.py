"""Exercise a sweep case's physical outcome branches on textual CPU sources."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from physical_walk_audit import LIFECYCLE, check_lifecycle, classify


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(suffix, kind):
    if suffix not in {f'right_of_way_physical_context-{n:04d}' for n in range(4)}:
        raise ValueError('Unknown staged sweep case')
    manifest = json.loads((HERE / 'sweep-proof-bound-promotion-candidate.json').read_text())
    case_id = HERE.name + '__' + suffix
    entry = next(item for item in manifest['cases'] if item['case_id'] == case_id)
    base = {'case_id': case_id, 'construction_sha256': entry['construction_sha256'],
            'cpu_fixture_mock': True, 'mock_input_provenance': 'synthetic_native_sample',
            'original_native_motion_verified': False, 'original_walk_pixels_verified': False,
            'accepted': False, 'legal_verdict_claimed': False,
            'diagnostic_spec_sha256': sha(HERE / 'update028-sweep-diagnostic.json')}
    if kind == 'lifecycle':
        events = list(LIFECYCLE)
        check_lifecycle(events)
        damaged = events.copy()
        damaged[-2:] = reversed(damaged[-2:])
        try:
            check_lifecycle(damaged)
        except ValueError:
            pass
        else:
            raise ValueError('Premature saved processing accepted')
        return {**base, 'events': events, 'exit_code': 0,
                'actual_owner_release_verified': False}
    source = json.loads((HERE / 'update028-sweep-diagnostic.json').read_text())['files']
    names = ('native_samples.jsonl', 'video_frames.jsonl', 'road_geometry.json')
    samples = [json.loads(line) for line in source[names[0]].splitlines()]
    mapping = [json.loads(line) for line in source[names[1]].splitlines()]
    geometry = json.loads(source[names[2]])
    if (geometry.get('synthetic_diagnostic') is not True or
            any(row.get('speed_provenance') != 'synthetic_native_sample' for row in samples)):
        raise ValueError('Diagnostic source provenance changed')
    if kind == 'incomplete_motion':
        samples = copy.deepcopy(samples)
        for sample in samples:
            sample['pedestrian_body_xy_m'] = [[-5.2, -11.2], [-4.8, -11.2],
                                              [-4.8, -10.8], [-5.2, -10.8]]
    elif kind == 'missing_evidence':
        mapping = mapping[:-1]
    try:
        measured = classify(samples, mapping, geometry, suffix)
        status = measured['status']
    except ValueError:
        if kind != 'missing_evidence':
            raise
        measured, status = {}, 'unverified'
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    if status != expected:
        raise ValueError(f'Sweep mock branch differs: {suffix} {kind} {status}')
    return {**base, 'physical_checks': {'maneuver': {
                'status': status,
                'method': '480-frame synthetic source-shape Walk/bus response classifier',
                'sources': list(names)}},
            'maneuver_completed': status == 'met',
            'realized_observables': measured if status == 'met' else {},
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'mock_native_branch_only': True,
            'source_text_sha256': {name: hashlib.sha256(source[name].encode()).hexdigest()
                                   for name in names}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion',
                                          'missing_evidence', 'lifecycle'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = run(args.case, args.kind)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps({'case_id': value['case_id'], 'kind': args.kind,
                      'status': value.get('physical_checks', {}).get('maneuver', {}).get('status'),
                      'cpu_fixture_mock': True, 'original_native_motion_verified': False}))
