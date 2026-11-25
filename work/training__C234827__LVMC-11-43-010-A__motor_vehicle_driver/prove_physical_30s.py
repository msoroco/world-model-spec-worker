"""Produce independent synthetic rotary completion and lifecycle CPU receipts."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
EVALUATOR = FOLDER / 'physical_preparation_30s.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    manifest = json.loads((FOLDER / 'selected-probe-manifest.json').read_text())
    for index, entry in enumerate(manifest['cases'], 1):
        case = entry['case_id']
        proof_dir = FOLDER / 'physical-proof' / f'witness_{index}'
        proof_dir.mkdir(parents=True, exist_ok=True)
        complete = FOLDER / 'selected-source' / f'witness_{index}' / 'native-raw-actors.jsonl'
        incomplete = proof_dir / 'incomplete-source.jsonl'
        incomplete.write_text('\n'.join(complete.read_text().splitlines()[:100]) + '\n')
        cases = [('complete_motion', complete), ('incomplete_motion', incomplete),
                 ('missing_evidence', proof_dir / 'absent-native-raw-actors.jsonl')]
        fixtures = []
        for kind, source in cases:
            result = proof_dir / f'{kind}-result.json'
            log = proof_dir / f'{kind}.log'
            command = [sys.executable, str(EVALUATOR), '--source', str(source),
                       '--case', case, '--output', str(result)]
            completed = subprocess.run(command, text=True, capture_output=True, check=False)
            log.write_text((completed.stdout + completed.stderr).rstrip() + '\n')
            if completed.returncode:
                raise ValueError(f'{kind} failed: {completed.stderr}')
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            actual = json.loads(result.read_text())['physical_checks']['maneuver']['status']
            if actual != expected:
                raise ValueError(f'{kind}: expected {expected}, got {actual}')
            fixtures.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                             'log': log.relative_to(FOLDER).as_posix(), 'log_sha256': sha(log),
                             'result': result.relative_to(FOLDER).as_posix(),
                             'result_sha256': sha(result)})
        lifecycle_log = proof_dir / 'lifecycle.log'
        saved = FOLDER / 'selected-proofs' / f'witness_{index}-primary-processing.json'
        processing = json.loads(saved.read_text())
        if not (processing['passed'] and processing['recorded_only'] and
                processing['originals_preserved'] and processing['timestamp_joins']['passed']):
            raise ValueError('Saved processing did not preserve the diagnostic acquisition')
        events = ['capture_finished', 'encoders_closed', 'restoration_verified',
                  'native_exit', 'owner_released', 'saved_processing_started']
        lifecycle_log.write_text('Synthetic lifecycle order for CPU proof: ' +
                                 ' -> '.join(events) + '\n' +
                                 'Recorded-only saved receipt preserves 600 frame joins; actual Native owner release remains a delivery action.\n')
        proof = {'case_id': case, 'construction_sha256': entry['construction_sha256'],
                 'fixtures': fixtures,
                 'lifecycle': {'events': events, 'exit_code': 0,
                               'log': lifecycle_log.relative_to(FOLDER).as_posix(),
                               'log_sha256': sha(lifecycle_log)},
                 'scope': 'synthetic CPU diagnostic; physical and legal delivery acceptance pending'}
        path = proof_dir / 'proof.json'
        write(path, proof)
        entry['physical_preparation'] = {'case_id': case,
                                         'receipt': path.relative_to(FOLDER).as_posix(),
                                         'sha256': sha(path)}
        print(case, 'physical fixtures', len(fixtures))
    (FOLDER / 'selected-probe-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
