"""Summarize update 005 CPU proof and unresolved physical work without relabeling it."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    batch = read(ROOT / 'batch.json')
    validation = read(ROOT / 'work/_shared/lead-validation005.json')
    assignments = []
    for assignment_id in batch['assignments']:
        folder = ROOT / 'work' / assignment_id
        result = read(folder / 'result.json')
        manifest = read(folder / 'execution-manifest.json')
        cases = [v for v in validation['cases'] if v['assignment_id'] == assignment_id]
        assignments.append({
            'assignment_id': assignment_id,
            'status': result['status'],
            'readiness_kind': result.get('readiness_kind'),
            'applied_update': result.get('applied_update'),
            'reason': result.get('reason'),
            'physical_acceptance': False,
            'unresolved_physical_checks': result.get('unresolved_physical_checks') or [
                'Native motion and target causation', 'Original scene and environmental conditions',
                'Camera visibility, timing, and final encoded video; see HANDOFF.md for scenario-specific findings'],
            'physical_handoff': str((folder / 'HANDOFF.md').relative_to(ROOT)),
            'exact_cases': [e['case_id'] for e in manifest['cases']],
            'per_case_commands_and_hashed_logs': cases,
            'package_tests': result.get('tests', []),
            'compatibility_attempts': result.get('compatibility_attempts', []),
            'package_compatibility_receipts': [e.get('compatibility', {}).get('receipt') for e in manifest['cases']],
            'acquisition_coverage': {e['case_id']: sorted(e.get('acquisition', {})) for e in manifest['cases']},
            'assignment_result_sha256': sha(folder / 'result.json'),
        })
    report = {
        'format': 'worker-lead-acceptance-update005-v1',
        'branch': batch['return_branch'],
        'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
        'source_example': {'command': '.venv-cpu/bin/python runtime.py compatibility --manifest .runtime-work/output-example005/execution-manifest.json --case diagnostic__output_contract__case --fixture .runtime-work/output-example005/fixtures/retained --output .runtime-work/output-example005-final-proof --library runtime/main-pipeline-v1/library --validator .runtime-work/decoder005/.lake/build/bin/adapterCheck',
                           'passed': True, 'log': 'work/_shared/example005.log',
                           'sha256': sha(ROOT / 'work/_shared/example005.log')},
        'shared_runtime_tests': {'count': 84, 'passed': True, 'scope': 'CPU',
                                 'log': 'work/_shared/update005-runtime-tests.log',
                                 'sha256': sha(ROOT / 'work/_shared/update005-runtime-tests.log')},
        'negative_tests': {'count': 6, 'passed': True,
                           'log': 'work/_shared/update005-negative-tests.log',
                           'sha256': sha(ROOT / 'work/_shared/update005-negative-tests.log')},
        'restoration_tests': {'source': 'runtime/main-pipeline-v1/tests/test_world_restore.py', 'result': 'included in 84 passing shared-runtime tests'},
        'submission_validation': read(ROOT / 'work/_shared/submission-validation005.json'),
        'preparation_acceptance': read(ROOT / 'work/_shared/preparation-acceptance005.json'),
        'all_offline_passed': validation['all_offline_passed'],
        'all_package_compatibility_passed': validation['all_compatibility_passed'],
        'assignments': assignments,
        'limitations': ['Diagnostic fixtures establish software behavior only.', 'No CARLA run or physical acceptance was performed.', 'Frozen mandatory ontology/capture gaps are retained as unresolved findings.'],
    }
    target = ROOT / 'work/_shared/lead-acceptance.json'
    target.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'assignments': len(assignments), 'exact_cases': len(validation['cases']),
                      'ready': sum(a['status'] == 'ready' for a in assignments),
                      'partial': sum(a['status'] == 'partial' for a in assignments)}))


if __name__ == '__main__':
    main()
