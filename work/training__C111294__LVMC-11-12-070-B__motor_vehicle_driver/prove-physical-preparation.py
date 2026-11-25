"""Exercise complete, incomplete and absent physical CPU sources per exact case."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
EVALUATOR = HERE / 'physical-preparation.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        number = case.rsplit('_', 1)[-1]
        fixture = HERE / f'current-v2-probe-{number}-fixture'
        source, road = fixture / 'native_samples.jsonl', fixture / 'road.xodr'
        proof_dir = HERE / 'physical-proof' / f'probe_{number}'
        proof_dir.mkdir(parents=True, exist_ok=True)
        incomplete = proof_dir / 'incomplete-source.jsonl'
        incomplete.write_text('\n'.join(source.read_text().splitlines()[:100]) + '\n')
        fixtures = []
        for kind, candidate in [('complete_motion', source),
                                ('incomplete_motion', incomplete),
                                ('missing_evidence', proof_dir / 'absent-native-samples.jsonl')]:
            result = proof_dir / f'{kind}-result.json'
            log = proof_dir / f'{kind}.log'
            command = [sys.executable, str(EVALUATOR), '--source', str(candidate),
                       '--road', str(road), '--case', case, '--output', str(result)]
            done = subprocess.run(command, text=True, capture_output=True, check=False)
            log.write_text((done.stdout + done.stderr).rstrip() + '\n')
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            actual = json.loads(result.read_text())['physical_checks']['maneuver']['status']
            if done.returncode or actual != expected:
                raise ValueError(f'{kind}: expected {expected}, got {actual}: {done.stderr}')
            fixtures.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                             'log': log.relative_to(HERE).as_posix(), 'log_sha256': sha(log),
                             'result': result.relative_to(HERE).as_posix(),
                             'result_sha256': sha(result)})
        saved = json.loads((HERE / f'current-v2-probe-{number}-saved-proof.json').read_text())
        if not saved['processing_receipt']['recorded_only'] or not saved['source_hashes_preserved']:
            raise ValueError('Recorded-only source preservation missing')
        events = ['capture_finished', 'encoders_closed', 'restoration_verified',
                  'native_exit', 'owner_released', 'saved_processing_started']
        life_log = proof_dir / 'lifecycle.log'
        life_log.write_text('Synthetic CPU lifecycle order: ' + ' -> '.join(events) + '\n'
                            'Original Native owner release requires local delivery.\n')
        proof = {'case_id': case, 'construction_sha256': entry['construction_sha256'],
                 'fixtures': fixtures,
                 'lifecycle': {'events': events, 'exit_code': 0,
                               'log': life_log.relative_to(HERE).as_posix(),
                               'log_sha256': sha(life_log)},
                 'scope': 'source-shaped synthetic diagnostic; original full-body and legal acceptance pending'}
        path = proof_dir / 'proof.json'
        path.write_text(json.dumps(proof, indent=2) + '\n')
        entry['physical_preparation'] = {'case_id': case,
                                         'receipt': path.relative_to(HERE).as_posix(),
                                         'sha256': sha(path)}
        print(case, 'physical CPU outcomes passed')
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
