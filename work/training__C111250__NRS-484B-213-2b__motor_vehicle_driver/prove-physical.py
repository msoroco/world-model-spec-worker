"""Exercise full, truncated and missing intersection-body CPU fixtures."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

FOLDER = Path(__file__).resolve().parent
EVALUATOR = FOLDER / 'physical-preparation.py'
NAME = {'probe_01': 'primary', 'probe_02': 'contrast', 'probe_03': 'traversal'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = FOLDER / 'selected-probe-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        proof_dir = FOLDER / 'physical-proof' / suffix
        proof_dir.mkdir(parents=True, exist_ok=True)
        source_dir = FOLDER / f'current-v2-{NAME[suffix]}-sources'
        complete = source_dir / 'vehicle-footprints.jsonl'
        context = source_dir / 'road-context.json'
        incomplete = proof_dir / 'incomplete-source.jsonl'
        incomplete.write_text('\n'.join(complete.read_text().splitlines()[:100]) + '\n')
        fixtures = []
        for kind, source in [('complete_motion', complete), ('incomplete_motion', incomplete),
                             ('missing_evidence', proof_dir / 'absent-footprints.jsonl')]:
            result = proof_dir / f'{kind}-result.json'
            log = proof_dir / f'{kind}.log'
            command = [sys.executable, str(EVALUATOR), '--source', str(source),
                       '--context', str(context), '--case', case, '--output', str(result)]
            completed = subprocess.run(command, text=True, capture_output=True, check=False)
            log.write_text((completed.stdout + completed.stderr).rstrip() + '\n')
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            actual = json.loads(result.read_text())['physical_checks']['maneuver']['status']
            if completed.returncode or actual != expected:
                raise ValueError(f'{kind}: expected {expected}, got {actual}: {completed.stderr}')
            fixtures.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                             'log': log.relative_to(FOLDER).as_posix(), 'log_sha256': sha(log),
                             'result': result.relative_to(FOLDER).as_posix(),
                             'result_sha256': sha(result)})
        saved = json.loads((FOLDER / 'selected-proofs' / f'{suffix}-primary-processing.json').read_text())
        if not (saved['passed'] and saved['recorded_only'] and saved['originals_preserved']
                and saved['timestamp_joins']['passed']):
            raise ValueError('Recorded-only source preservation is unproven')
        events = ['capture_finished', 'encoders_closed', 'restoration_verified',
                  'native_exit', 'owner_released', 'saved_processing_started']
        lifecycle_log = proof_dir / 'lifecycle.log'
        lifecycle_log.write_text('Synthetic CPU lifecycle order: ' + ' -> '.join(events) + '\n'
                                 'Original Native owner release requires future local delivery.\n')
        proof = {'case_id': case, 'construction_sha256': entry['construction_sha256'],
                 'fixtures': fixtures, 'lifecycle': {'events': events, 'exit_code': 0,
                     'log': lifecycle_log.relative_to(FOLDER).as_posix(), 'log_sha256': sha(lifecycle_log)},
                 'scope': 'synthetic diagnostic; original Native and legal acceptance pending'}
        path = proof_dir / 'proof.json'
        path.write_text(json.dumps(proof, indent=2) + '\n')
        entry['physical_preparation'] = {'case_id': case, 'receipt': path.relative_to(FOLDER).as_posix(),
                                         'sha256': sha(path)}
        print(suffix, 'physical fixture outcomes passed')
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
