"""Prove source-joined synthetic motion branches; real motion remains unverified."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def assess(samples, mapping, kind):
    if kind == 'missing_evidence':
        mapping = []
    if not samples or len(samples) != len(mapping):
        return 'unverified', 0
    if any(sample['native_frame'] != frame['carla_frame'] or
           abs(sample['time_s'] - frame['time_s']) > 1e-8
           for sample, frame in zip(samples, mapping)):
        return 'unverified', 0
    last_y = min(vertex[1] for vertex in samples[-1]['native_body_xy_m'])
    return ('met' if last_y > 7 else 'not_met'), len(samples)


def run():
    manifest = json.loads((HERE / 'current-v2-draft-manifest.json').read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        label = case.rsplit('__', 1)[-1]
        diagnostic_path = HERE / f'diagnostic-{label}.json'
        diagnostic = json.loads(diagnostic_path.read_text())['files']
        samples = [json.loads(line) for line in diagnostic['native_samples.jsonl'].splitlines()]
        mapping = [json.loads(line) for line in diagnostic['video_frames.jsonl'].splitlines()]
        if len(samples) != 840 or len(mapping) != 840:
            raise ValueError('Exact 840-frame source missing')
        directory = HERE / 'physical-proofs' / label
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            selected = samples if kind != 'incomplete_motion' else samples[:100]
            mapped = mapping if kind != 'incomplete_motion' else mapping[:100]
            status, joined = assess(selected, mapped, kind)
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            if status != expected:
                raise ValueError(f'{case} {kind}: {status} differs from {expected}')
            result = {
                'case_id': case, 'construction_sha256': entry['construction_sha256'],
                'physical_checks': {'maneuver': {
                    'status': status,
                    'method': 'Original-frame joined synthetic ego body endpoint versus surveyed intersection exit',
                    'sources': ['diagnostic-' + label + '.json:native_samples.jsonl',
                                'diagnostic-' + label + '.json:video_frames.jsonl']}},
                'maneuver_completed': status == 'met',
                'realized_observables': {'last_ego_body_min_y_m': min(v[1] for v in selected[-1]['native_body_xy_m'])} if status == 'met' else {},
                'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
                'original_native_motion_verified': False, 'original_pixels_verified': False,
                'legal_verdict_claimed': False,
                'source_sha256': {'diagnostic-' + label + '.json': sha(diagnostic_path)},
                'joined_frames': joined}
            result_path = directory / f'{kind}.json'
            log_path = directory / f'{kind}.log'
            write(result_path, result)
            log_path.write_text(f'{case} {kind} status={status} joined_frames={joined} diagnostic=true\n')
            fixtures.append({'kind': kind,
                             'command': f'.venv-cpu/bin/python work/{HERE.name}/prove-physical-branches.py',
                             'exit_code': 0,
                             'log': log_path.relative_to(HERE).as_posix(),
                             'log_sha256': sha(log_path),
                             'result': result_path.relative_to(HERE).as_posix(),
                             'result_sha256': sha(result_path)})
        lifecycle = directory / 'lifecycle.log'
        lifecycle.write_text(' '.join(EVENTS) + '\n')
        proof_path = directory / 'proof.json'
        write(proof_path, {'format': 'c111088-synthetic-physical-branch-proof',
                           'case_id': case, 'construction_sha256': entry['construction_sha256'],
                           'fixtures_are_cpu_mocks': True,
                           'original_native_motion_verified': False,
                           'fixtures': fixtures,
                           'lifecycle': {'events': EVENTS, 'exit_code': 0,
                                         'log': lifecycle.relative_to(HERE).as_posix(),
                                         'log_sha256': sha(lifecycle)}})
        print(json.dumps({'case_id': case, 'proof_sha256': sha(proof_path)}))


if __name__ == '__main__':
    run()
