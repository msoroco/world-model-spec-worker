"""Exercise physical completion and ownership order with synthetic CPU rows."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_lifecycle(events):
    if events != EVENTS:
        raise ValueError('Saved processing preceded Native ownership closure')


def run(case, kind):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + case))
    base = {'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
            'cpu_fixture_mock': True, 'original_native_motion_verified': False,
            'original_pixels_verified': False, 'accepted': False, 'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        check_lifecycle(EVENTS)
        try:
            check_lifecycle(EVENTS[:-2] + list(reversed(EVENTS[-2:])))
        except ValueError:
            pass
        else:
            raise AssertionError('Premature saved processing accepted')
        return {**base, 'events': EVENTS, 'exit_code': 0}
    attempt = ROOT / '.runtime-work/c111256-current' / (case + '-primary') / 'compat'
    samples_path = attempt / 'native_samples.jsonl'
    mapping_path = attempt / 'video_frames.jsonl'
    samples = [json.loads(line) for line in samples_path.read_text().splitlines()]
    mapping = [json.loads(line) for line in mapping_path.read_text().splitlines()]
    assert len(samples) == len(mapping) == 600
    first_frame = samples[0]['native_frame']
    first_time = samples[0]['time_s']
    assert all(sample['native_frame'] == first_frame + index for index, sample in enumerate(samples))
    assert all(abs(sample['time_s'] - (first_time + index / 20)) < 1e-8 for index, sample in enumerate(samples))
    if kind == 'incomplete_motion':
        samples = samples[:200]
        mapping = mapping[:200]
    elif kind == 'missing_evidence':
        mapping = mapping[:-1]
    if len(samples) != len(mapping):
        status = 'unverified'
    else:
        status = 'met' if samples[-1]['native_center_xy_m'][1] > 13 else 'not_met'
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    assert status == expected, (case, kind, status)
    return {**base, 'physical_checks': {'maneuver': {
        'status': status,
        'method': 'Synthetic 20 Hz ego body departure and exact 600-frame saved join',
        'sources': ['native_samples.jsonl', 'video_frames.jsonl']}},
        'maneuver_completed': status == 'met',
        'realized_observables': {'last_ego_y_m': samples[-1]['native_center_xy_m'][1]} if status == 'met' else {},
        'provenance_kind': 'synthetic_fixture',
        'diagnostic_fixture': True,
        'synthetic_source_sha256': {'native_samples.jsonl': sha(samples_path),
                                     'video_frames.jsonl': sha(mapping_path)}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', choices=['complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = run(args.case, args.kind)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps({'case': args.case, 'kind': args.kind,
                      'status': value.get('physical_checks', {}).get('maneuver', {}).get('status'),
                      'cpu_fixture_mock': True}))
