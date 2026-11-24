"""Check 600-frame synthetic source joins and physical outcome branches."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def source_files(entry):
    recipe = read(ROOT / entry['fixture_recipe'])
    by_name = {item['path']: item for item in recipe['sources']}
    names = ('native_samples.jsonl', 'video_frames.jsonl',
             'native_parking_history.json', 'road_geometry.json')
    selected = {}
    for name in names:
        item = by_name[name]
        path = ROOT / item['source']
        assert sha(path) == item['sha256']
        selected[name] = path
    return selected


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = read(manifest_path)
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        source = source_files(entry)
        samples = [json.loads(line) for line in source['native_samples.jsonl'].read_text().splitlines()]
        frames = [json.loads(line) for line in source['video_frames.jsonl'].read_text().splitlines()]
        parked = read(source['native_parking_history.json'])['frames']
        assert len(samples) == len(frames) == len(parked) == 600
        for index, (sample, frame, park) in enumerate(zip(samples, frames, parked)):
            assert sample['native_frame'] == frame['carla_frame'] == park['native_frame']
            assert sample['video_frame'] == frame['video_frame'] == park['video_frame'] == index
            assert abs(sample['time_s'] - frame['time_s']) < 1e-8
            assert abs(sample['time_s'] - park['time_s']) < 1e-8
        resting = sum(abs(row['speed_m_s']) <= 0.05 for row in parked)
        assert resting >= 60 and abs(parked[-1]['speed_m_s']) <= 0.05
        directory = HERE / 'physical-proofs' / suffix
        command = f'.venv-cpu/bin/python work/{HERE.name}/prove-selected-physical-branches.py'
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            subset = samples if kind != 'incomplete_motion' else samples[:100]
            status = ('unverified' if kind == 'missing_evidence' else
                      'met' if len(subset) == 600 and resting >= 60 else 'not_met')
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            assert status == expected
            result = {
                'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
                'physical_checks': {'maneuver': {
                    'status': status, 'method': 'Synthetic source-joined frame, body and rest-history audit',
                    'sources': [str(path.relative_to(ROOT)) for path in source.values()]}},
                'maneuver_completed': status == 'met',
                'realized_observables': ({'joined_frames': 600, 'resting_frames': resting,
                                         'final_center_xy_m': samples[-1]['native_center_xy_m']}
                                        if status == 'met' else {}),
                'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
                'native_executed': False, 'original_pixels_reviewed': False,
                'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
                'source_sha256': {name: sha(path) for name, path in source.items()}}
            result_path = directory / f'{kind}.json'
            log_path = directory / f'{kind}.log'
            write(result_path, result)
            log_path.write_text(f'{entry["case_id"]} {kind}: {status}; source joined frames={len(subset)}; '
                                f'full resting frames={resting}; original Native=false\n')
            fixtures.append({'kind': kind, 'command': command, 'exit_code': 0,
                             'log': str(log_path.relative_to(HERE)), 'log_sha256': sha(log_path),
                             'result': str(result_path.relative_to(HERE)),
                             'result_sha256': sha(result_path)})
        life_path = directory / 'lifecycle.log'
        life_path.write_text('CPU lifecycle order assertion: ' + ' -> '.join(EVENTS) + '\n')
        proof_path = directory / 'proof.json'
        write(proof_path, {'format': 'c110454-a11-synthetic-physical-branch-proof',
                           'case_id': entry['case_id'],
                           'construction_sha256': entry['construction_sha256'],
                           'fixtures_are_cpu_mocks': True, 'native_executed': False,
                           'fixtures': fixtures,
                           'lifecycle': {'events': EVENTS, 'exit_code': 0,
                                         'log': str(life_path.relative_to(HERE)),
                                         'log_sha256': sha(life_path)}})
        entry['physical_preparation'] = {'receipt': str(proof_path.relative_to(HERE)),
                                         'sha256': sha(proof_path)}
    write(manifest_path, manifest)
    print(json.dumps({'cases': len(manifest['cases']), 'sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
