"""Exercise signal-entry motion, missing evidence and lifecycle branches on CPU rows."""
import argparse
import copy
import hashlib
import json
import tempfile
from pathlib import Path

from physical_signal_audit import LIFECYCLE, audit_original, check_lifecycle, classify

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha_text(text):
    return hashlib.sha256(text.encode()).hexdigest()


def run(case, kind):
    manifest = json.loads((HERE / 'current-runtime-reproof-manifest.json').read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'].endswith('__' + case))
    base = {'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
            'cpu_fixture_mock': True, 'mock_input_provenance': 'synthetic_cpu_fixture',
            'original_native_motion_verified': False, 'accepted': False,
            'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        check_lifecycle(list(LIFECYCLE))
        try:
            check_lifecycle(LIFECYCLE[:-2] + list(reversed(LIFECYCLE[-2:])))
        except ValueError:
            pass
        else:
            raise ValueError('Premature saved processing accepted')
        return {**base, 'events': LIFECYCLE, 'exit_code': 0,
                'actual_owner_release_verified': False}
    source = (ROOT / '.runtime-work/c111331-current-reference-primary-compat' if case == 'reference' else ROOT / '.runtime-work/c111331-current-matrix/contrast/primary/compat')
    raw_samples = (source / 'native_samples.jsonl').read_text()
    raw_frames = (source / 'video_frames.jsonl').read_text()
    samples = [json.loads(line) for line in raw_samples.splitlines()]
    frames = [json.loads(line) for line in raw_frames.splitlines()]
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work', prefix='c111331-original-negative-') as temporary:
        folder = Path(temporary)
        (folder / 'native_samples.jsonl').write_text(raw_samples)
        (folder / 'video_frames.jsonl').write_text(raw_frames)
        try:
            audit_original(folder)
        except ValueError as exc:
            if 'Original Native signal/body source required' not in str(exc):
                raise
        else:
            raise ValueError('Synthetic signal/body source accepted as original')
    if kind == 'incomplete_motion':
        samples = copy.deepcopy(samples)
        first_center = samples[0]['native_center_xy_m']
        first_body = samples[0]['native_body_xy_m']
        for row in samples:
            row['native_center_xy_m'] = first_center
            row['native_body_xy_m'] = first_body
    elif kind == 'missing_evidence':
        frames = frames[:-1]
    result = classify(samples, frames)
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    if result['status'] != expected:
        raise ValueError('Physical fixture branch differs: ' + kind + ' ' + result['status'])
    return {**base, 'physical_checks': {'maneuver': {
                'status': result['status'],
                'method': 'Independent 480-frame Native-shaped body, phase and video-join classifier',
                'sources': ['native_samples.jsonl', 'video_frames.jsonl']}},
            'maneuver_completed': result['status'] == 'met',
            'realized_observables': result if result['status'] == 'met' else {},
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'mock_native_branch_only': True,
            'original_production_audit_rejected': True,
            'source_sha256': {'native_samples.jsonl': sha_text(raw_samples),
                              'video_frames.jsonl': sha_text(raw_frames)}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('reference', 'contrast'), required=True)
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion',
                                          'missing_evidence', 'lifecycle'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.case, args.kind)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': result['case_id'], 'kind': args.kind,
                      'status': result.get('physical_checks', {}).get('maneuver', {}).get('status'),
                      'cpu_fixture_mock': True}))
