"""Exercise independent speed-completion branches on synthetic source rows."""
import argparse
import copy
import hashlib
import json
import tempfile
from pathlib import Path

from physical_speed_audit import LIFECYCLE, audit_original, check_lifecycle, classify

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REQUESTS = {'below_80_mph': 75.0, 'inside_80_mph': 79.5,
            'at_80_mph': 80.0, 'above_80_mph': 85.0}


def sha_text(text):
    return hashlib.sha256(text.encode()).hexdigest()


def run(suffix, kind):
    manifest = json.loads((HERE / 'current-runtime-reproof-manifest.json').read_text())
    case_id = HERE.name + '__' + suffix
    entry = next(item for item in manifest['cases'] if item['case_id'] == case_id)
    base = {'case_id': case_id, 'construction_sha256': entry['construction_sha256'],
            'cpu_fixture_mock': True, 'mock_input_provenance': 'synthetic_cpu_fixture',
            'original_native_motion_verified': False, 'original_speed_verified': False,
            'accepted': False, 'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        events = list(LIFECYCLE)
        assert check_lifecycle(events)['saved_processing_after_owner_release']
        wrong = events.copy()
        wrong[-2:] = reversed(wrong[-2:])
        try:
            check_lifecycle(wrong)
        except ValueError:
            pass
        else:
            raise ValueError('Premature saved processing accepted')
        return {**base, 'events': events, 'exit_code': 0,
                'actual_owner_release_verified': False}
    source = (ROOT / '.runtime-work/c111294-current-below-primary-compat' if suffix == 'below_80_mph' else ROOT / '.runtime-work/c111294-current-matrix' / suffix / 'primary/compat')
    raw_samples = (source / 'native_samples.jsonl').read_text()
    raw_frames = (source / 'video_frames.jsonl').read_text()
    rows = lambda text: [json.loads(line) for line in text.splitlines() if line.strip()]
    samples, frames = rows(raw_samples), rows(raw_frames)
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work',
                                     prefix='c111294-original-negative-') as temporary:
        folder = Path(temporary)
        (folder / 'native_samples.jsonl').write_text(raw_samples)
        (folder / 'video_frames.jsonl').write_text(raw_frames)
        try:
            audit_original(folder, REQUESTS[suffix])
        except ValueError as exc:
            if 'Original Native speed source required' not in str(exc):
                raise
        else:
            raise ValueError('Synthetic velocity accepted as original')
    if kind == 'incomplete_motion':
        samples = copy.deepcopy(samples)
        fixed = samples[0]['ego_position_m']
        for sample in samples:
            sample['ego_velocity_mps'] = [0.0, 0.0, 0.0]
            sample['ego_position_m'] = fixed
    elif kind == 'missing_evidence':
        frames = frames[:-1]
    try:
        measured = classify(samples, frames, REQUESTS[suffix])
        status = measured['status']
    except ValueError:
        if kind != 'missing_evidence':
            raise
        measured, status = {}, 'unverified'
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    if status != expected:
        raise ValueError('Physical branch differs: ' + kind + ' ' + status)
    return {**base, 'physical_checks': {'maneuver': {
                'status': status,
                'method': 'Independent 480-frame Native-shaped velocity, pose and frame-join classifier',
                'sources': ['native_samples.jsonl', 'video_frames.jsonl']}},
            'maneuver_completed': status == 'met',
            'realized_observables': measured if status == 'met' else {},
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'mock_native_branch_only': True,
            'original_production_audit_rejected': True,
            'source_sha256': {'native_samples.jsonl': sha_text(raw_samples),
                              'video_frames.jsonl': sha_text(raw_frames)}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=tuple(REQUESTS), required=True)
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion',
                                          'missing_evidence', 'lifecycle'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = run(args.case, args.kind)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps({'case_id': value['case_id'], 'kind': args.kind,
                      'status': value.get('physical_checks', {}).get('maneuver', {}).get('status'),
                      'cpu_fixture_mock': True}))
