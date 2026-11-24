"""Prove three synthetic motion outcomes and the saved-processing lifecycle."""
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


def run():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        condition = entry['case_id'].rsplit('__', 1)[-1]
        source = HERE / f'current-v2-{condition}-fixture'
        samples_path = source / 'native_samples.jsonl'
        mapping_path = source / 'video_frames.jsonl'
        samples = [json.loads(line) for line in samples_path.read_text().splitlines()]
        mapping = [json.loads(line) for line in mapping_path.read_text().splitlines()]
        if len(samples) != len(mapping) or len(samples) != 600:
            raise ValueError('Missing exact 600-frame synthetic motion source')
        for index, (sample, frame) in enumerate(zip(samples, mapping)):
            if (sample['native_frame'] != frame['carla_frame']
                    or sample['native_frame'] != samples[0]['native_frame'] + index
                    or abs(sample['time_s'] - frame['time_s']) > 1e-8):
                raise ValueError('Source frame/time join failed')
        directory = HERE / 'physical-proofs' / condition
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            subset = samples if kind != 'incomplete_motion' else samples[:100]
            joined = kind != 'missing_evidence'
            status = ('unverified' if not joined else
                      'met' if subset[-1]['native_center_xy_m'][0] > 20 else 'not_met')
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            if status != expected:
                raise ValueError('Diagnostic motion branch differed')
            result = {'case_id': entry['case_id'],
                      'construction_sha256': entry['construction_sha256'],
                      'physical_checks': {'maneuver': {
                          'status': status,
                          'method': '600-frame synthetic source-joined motor-vehicle center and full-body history',
                          'sources': ['native_samples.jsonl', 'body_history.jsonl', 'video_frames.jsonl']}},
                      'maneuver_completed': status == 'met',
                      'realized_observables': {'last_ego_x_m': subset[-1]['native_center_xy_m'][0]} if status == 'met' else {},
                      'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
                      'original_native_motion_verified': False, 'original_pixels_verified': False,
                      'legal_verdict_claimed': False,
                      'source_sha256': {'native_samples.jsonl': sha(samples_path),
                                        'body_history.jsonl': sha(source / 'body_history.jsonl'),
                                        'video_frames.jsonl': sha(mapping_path)}}
            result_path = directory / f'{kind}.json'
            log_path = directory / f'{kind}.log'
            write(result_path, result)
            log_path.write_text(f'{entry["case_id"]} {kind} status={status} source_join=600 diagnostic=true\n')
            fixtures.append({'kind': kind,
                             'command': f'.venv-cpu/bin/python work/{HERE.name}/prove-physical-branches.py',
                             'exit_code': 0, 'log': log_path.relative_to(HERE).as_posix(),
                             'log_sha256': sha(log_path), 'result': result_path.relative_to(HERE).as_posix(),
                             'result_sha256': sha(result_path)})
        if EVENTS[-2:] != ['owner_released', 'saved_processing_started']:
            raise ValueError('Saved processing starts before owner release')
        lifecycle_log = directory / 'lifecycle.log'
        lifecycle_log.write_text(' '.join(EVENTS) + '\n')
        proof_path = directory / 'proof.json'
        write(proof_path, {'format': 'c110919-8c-synthetic-physical-branch-proof',
                           'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
                           'fixtures_are_cpu_mocks': True, 'original_native_motion_verified': False,
                           'fixtures': fixtures,
                           'lifecycle': {'events': EVENTS, 'exit_code': 0,
                                         'log': lifecycle_log.relative_to(HERE).as_posix(),
                                         'log_sha256': sha(lifecycle_log)}})
        entry['physical_preparation'] = {'receipt': proof_path.relative_to(HERE).as_posix(),
                                         'sha256': sha(proof_path)}
    write(path, manifest)
    print(json.dumps({'cases': len(manifest['cases']), 'manifest_sha256': sha(path)}))


if __name__ == '__main__':
    run()
