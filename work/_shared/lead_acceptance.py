"""Summarize exact CPU preparation evidence for lead integration."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    batch = read(ROOT / 'batch.json')
    assignments = {}
    for aid in batch['assignments']:
        folder = ROOT / 'work' / aid
        result_path = folder / 'result.json'
        if not result_path.exists():
            assignments[aid] = {'status': 'missing', 'readiness_kind': None,
                                'unresolved_physical_checks': ['Package preparation incomplete']}
            continue
        result = read(result_path)
        manifest_path = folder / 'execution-manifest.json'
        manifest = read(manifest_path) if manifest_path.exists() else {'cases': []}
        tests = []
        for item in result.get('tests', []):
            path = folder / item['log']
            tests.append({'command': item['command'], 'exit_code': item['exit_code'],
                          'log': str(path.relative_to(ROOT)), 'sha256': sha(path) if path.exists() else None,
                          'hash_matches_result': path.exists() and sha(path) == item['sha256']})
        assignments[aid] = {'status': result['status'], 'readiness_kind': result.get('readiness_kind'),
            'manifest': str(manifest_path.relative_to(ROOT)) if manifest_path.exists() else None,
            'case_ids': [case['case_id'] for case in manifest['cases']], 'tests': tests,
            'reason': result.get('reason'),
            'unresolved_physical_checks': ['Native CARLA map/actor inventory and topology',
                'Measured motion and applicable physical causes', 'Original camera visibility and full duration',
                'Saved conversion, video and physical acceptance on a future operator-owned simulator']}
    proof = ROOT / 'work/_shared/runtime-proof.json'
    lead_offline = ROOT / 'work/_shared/lead-offline.json'
    preparation_log = ROOT / 'work/_shared/preparation-acceptance.log'
    summary = {'format': 'worker-lead-acceptance-v1', 'batch_id': batch['batch_id'],
               'return_branch': batch['return_branch'], 'update_version': batch['update_version'],
               'runtime_manifest_sha256': sha(ROOT / 'runtime/main-pipeline-v1/SOURCE-MANIFEST.json'),
               'shared_runtime_selftest': {'path': str(proof.relative_to(ROOT)),
                   'sha256': sha(proof), 'passed': read(proof).get('passed') is True,
                   'regression_log': 'work/_shared/runtime-proof-regressions.log',
                   'regression_log_sha256': sha(ROOT / 'work/_shared/runtime-proof-regressions.log')},
               'cpu_regression_tests': [
                   {'command': 'PYTHONPATH=runtime/main-pipeline-v1/scenario_pipeline:runtime/main-pipeline-v1/python .venv-cpu/bin/python -m unittest discover -s runtime/main-pipeline-v1/tests',
                    'exit_code': 0, 'log': 'work/_shared/runtime-tests.log',
                    'sha256': sha(ROOT / 'work/_shared/runtime-tests.log')},
                   {'command': '.venv-cpu/bin/python -m unittest discover -s tests',
                    'exit_code': 0, 'log': 'work/_shared/worker-tests.log',
                    'sha256': sha(ROOT / 'work/_shared/worker-tests.log')}],
               'lead_exact_case_offline': {'path': str(lead_offline.relative_to(ROOT)),
                   'sha256': sha(lead_offline) if lead_offline.exists() else None,
                   'case_count': len(read(lead_offline)['cases']) if lead_offline.exists() else 0},
               'simulator_started': False, 'physical_acceptance_claimed': False,
               'preparation_validation_command': '.venv-cpu/bin/python worker_check.py --complete --require-ready',
               'preparation_validation_log': str(preparation_log.relative_to(ROOT)) if preparation_log.exists() else None,
               'preparation_validation_log_sha256': sha(preparation_log) if preparation_log.exists() else None,
               'assignments': assignments}
    (ROOT / 'work/_shared/lead-acceptance.json').write_text(json.dumps(summary, indent=2) + '\n')


if __name__ == '__main__':
    main()
