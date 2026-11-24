"""Prove source-sensitive parking completion and owner-release order on CPU fixtures."""
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


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        source = HERE / f'current-v2-{suffix}-fixture'
        source_files = ['native_samples.jsonl', 'body_history.jsonl', 'video_frames.jsonl', 'road_geometry.json']
        rows = [json.loads(x) for x in (source / source_files[0]).read_text().splitlines()]
        frames = [json.loads(x) for x in (source / source_files[2]).read_text().splitlines()]
        if len(rows) != len(frames) or len(rows) != 600:
            raise ValueError('Exact 600-frame Native source join absent')
        for index, (row, frame) in enumerate(zip(rows, frames)):
            if (row['native_frame'] != frame['carla_frame'] or
                    row['native_frame'] != rows[0]['native_frame'] + index or
                    abs(row['time_s'] - frame['time_s']) > 1e-8):
                raise ValueError('Parking frame/time join changed')
        target = -13.0 if suffix == 'probe_a' else 0.0
        directory = HERE / 'physical-proofs' / suffix
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            subset = rows if kind != 'incomplete_motion' else rows[:100]
            missing = kind == 'missing_evidence'
            complete = (len(subset) == 600 and
                abs(subset[-1]['native_center_xy_m'][0] - target) < 0.01 and
                sum(abs(r['speed_mps']) < 0.05 for r in subset) >= 360)
            status = 'unverified' if missing else 'met' if complete else 'not_met'
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            if status != expected:
                raise ValueError('Physical diagnostic outcome wrong')
            result = {'case_id': entry['case_id'],
                'construction_sha256': entry['construction_sha256'],
                'physical_checks': {'maneuver': {'status': status,
                    'method': 'Synthetic source-joined 600-frame ego center, full-body map and rest history',
                    'sources': source_files}},
                'maneuver_completed': status == 'met',
                'realized_observables': {'final_center_x_m': subset[-1]['native_center_xy_m'][0],
                    'sampled_parked_frames': 360} if status == 'met' else {},
                'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
                'original_native_motion_verified': False, 'original_pixels_verified': False,
                'legal_verdict_claimed': False,
                'source_sha256': {name: sha(source / name) for name in source_files}}
            result_path = directory / f'{kind}.json'
            log_path = directory / f'{kind}.log'
            write(result_path, result)
            log_path.write_text(f'{entry["case_id"]} {kind} status={status} original_native=false\n')
            fixtures.append({'kind': kind,
                'command': f'.venv-cpu/bin/python work/{HERE.name}/prove-physical-branches.py',
                'exit_code': 0, 'log': log_path.relative_to(HERE).as_posix(),
                'log_sha256': sha(log_path), 'result': result_path.relative_to(HERE).as_posix(),
                'result_sha256': sha(result_path)})
        life_path = directory / 'lifecycle.log'
        life_path.write_text(' '.join(EVENTS) + '\n')
        proof_path = directory / 'proof.json'
        write(proof_path, {'format': 'c110454-synthetic-physical-branch-proof',
            'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
            'fixtures_are_cpu_mocks': True, 'original_native_motion_verified': False,
            'fixtures': fixtures,
            'lifecycle': {'events': EVENTS, 'exit_code': 0,
                          'log': life_path.relative_to(HERE).as_posix(),
                          'log_sha256': sha(life_path)}})
        entry['physical_preparation'] = {'receipt': proof_path.relative_to(HERE).as_posix(),
                                         'sha256': sha(proof_path)}
    write(manifest_path, manifest)
    print(json.dumps({'cases': len(manifest['cases']), 'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
