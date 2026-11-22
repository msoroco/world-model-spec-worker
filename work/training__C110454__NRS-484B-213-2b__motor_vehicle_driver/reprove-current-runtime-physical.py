"""Rebuild nine selected physical CPU fixture receipts from current attempts."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
output_root = os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT')
if not output_root or ROOT / '.runtime-work' not in Path(output_root).resolve().parents:
    raise RuntimeError('Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first')
sys.path.insert(0, str(ROOT / 'runtime/pipeline'))
from scenario_pipeline.worker_exchange.physical_preparation import validate


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = HERE / 'current-runtime-reproof-manifest.json'
    entries = json.loads(manifest.read_text())['cases']
    if len(entries) != 9:
        raise ValueError('Nine selected cases required')
    rows = []
    for entry in entries:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        matches = sorted((ROOT / '.runtime-work').glob(
            f'c110454-current-{suffix}-primary-*-compat'))
        matches = [p for p in matches if (p / 'compatibility.json').is_file()]
        if not matches:
            raise ValueError('Current compatibility source missing: ' + suffix)
        attempt = max(matches, key=lambda p: p.stat().st_mtime_ns)
        folder = HERE / 'current-runtime-selected-physical' / suffix
        folder.mkdir(parents=True, exist_ok=True)
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle'):
            result, log = folder / (kind + '.json'), folder / (kind + '.log')
            cmd = [sys.executable, str(HERE / 'run-physical-fixture-current.py'),
                   '--manifest', str(manifest), '--attempt', str(attempt),
                   '--case', entry['case_id'], '--kind', kind, '--output', str(result)]
            run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            log.write_text(run.stdout + run.stderr)
            if run.returncode or not result.is_file():
                raise ValueError('Physical CPU fixture failed: ' + suffix + '/' + kind + ' ' + log.read_text())
            if kind == 'lifecycle':
                lifecycle = {'events': json.loads(result.read_text())['events'],
                             'exit_code': 0, 'log': str(log.relative_to(HERE)),
                             'log_sha256': sha(log)}
            else:
                value = json.loads(result.read_text())
                if value['cpu_fixture_mock'] is not True or value['original_native_motion_verified'] is not False:
                    raise ValueError('Physical fixture provenance differs')
                fixtures.append({'kind': kind, 'command': ' '.join(cmd), 'exit_code': 0,
                                 'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                                 'result': str(result.relative_to(HERE)), 'result_sha256': sha(result)})
        proof = {'format': 'c110454-physical-preparation-cpu-fixtures-v1',
                 'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
                 'fixtures_are_cpu_mocks': True, 'original_native_motion_verified': False,
                 'original_recordings_accepted': 0, 'fixtures': fixtures, 'lifecycle': lifecycle}
        path = folder / 'proof.json'
        path.write_text(json.dumps(proof, indent=2) + '\n')
        validate(ROOT, HERE, {**entry, 'physical_preparation': {
            'receipt': str(path.relative_to(HERE)), 'sha256': sha(path)}})
        rows.append({'case_id': entry['case_id'], 'receipt': str(path.relative_to(HERE)),
                     'sha256': sha(path)})
        print(suffix, 'physical CPU fixtures passed', flush=True)
    index = {'format': 'c110454-current-runtime-physical-v1',
             'manifest_sha256': sha(manifest), 'selected_cases': len(rows),
             'synthetic_outcome_branches': 3 * len(rows), 'lifecycle_fixtures': len(rows),
             'cases': rows, 'original_native_motion_verified': False}
    output = HERE / 'current-runtime-selected-physical-index.json'
    output.write_text(json.dumps(index, indent=2) + '\n')


if __name__ == '__main__':
    main()
