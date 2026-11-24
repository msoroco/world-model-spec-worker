"""Refresh truthful CPU coverage and exact test bindings for C229597."""
import hashlib
import json
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[1]
RESULT = PACKAGE / 'result.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    result = json.loads(RESULT.read_text())
    manifest = json.loads((PACKAGE / 'execution-manifest.json').read_text())
    plan = json.loads((PACKAGE / 'case-plan.json').read_text())
    result['status'] = 'partial'
    result['readiness_kind'] = None
    result['reason'] = ('Eight exact selected cases, including six canonical source-planned physical sweep cases, '
                        'pass pinned CPU offline, public positive/negative compatibility, synthetic saved processing, '
                        'physical preparation and delivery source audits. Three planned comparisons pass fixed-condition '
                        'and missing-case CPU audits. Native motion, actual camera pixels, highway classification, '
                        'exhibition judgment and legal outcomes remain unverified.')
    result['cases_planned'] = len(plan['cases'])
    result['cases_selected'] = len(manifest['cases'])
    result['candidate_plans_proven'] = sum(1 + len(entry['candidates']) for entry in manifest['cases'])
    result['comparison_audits_passed'] = len(plan['comparisons'])
    result['carla_executed'] = False
    result['recordings_accepted'] = 0
    case = manifest['cases'][0]['case_id']
    result['first_gpu_delivery_command'] = ('PYTHONPATH=runtime/scenario_pipeline python3.11 -m worker_exchange '
        'execute-delivery --repo . --batch full-train-delivery --db $DB --assignment '
        + PACKAGE.name + ' --case ' + case +
        ' --run $RUN --job $JOB_ID --python $CARLA_PYTHON --host $CARLA_HOST --port $CARLA_PORT')
    tests = list(result.get('tests', []))
    existing = {item['log'] for item in tests}
    for comparison in plan['comparisons']:
        audit = comparison['cpu_audit']
        for command_key, exit_key, log_key, hash_key in (
                ('command', 'positive_exit_code', 'positive_log', 'positive_log_sha256'),):
            log = audit[log_key]
            if log not in existing:
                tests.append({'command': audit[command_key], 'exit_code': audit[exit_key],
                              'log': log, 'sha256': audit[hash_key]})
                existing.add(log)
    for entry in manifest['cases']:
        post = entry['post_capture']
        log = post['test_log']
        if log not in existing:
            tests.append({'command': post['command'], 'exit_code': 0,
                          'log': log, 'sha256': sha(PACKAGE / log)})
            existing.add(log)
    result['tests'] = tests
    result['current_cpu_delivery'] = {
        'execution_manifest': 'execution-manifest.json',
        'execution_manifest_sha256': sha(PACKAGE / 'execution-manifest.json'),
        'case_plan': 'case-plan.json', 'case_plan_sha256': sha(PACKAGE / 'case-plan.json'),
        'cases': len(manifest['cases']), 'candidates': result['candidate_plans_proven'],
        'positive_negative_compatibility_receipts': result['candidate_plans_proven'],
        'saved_processing_receipts': len(manifest['cases']),
        'comparison_audits': len(plan['comparisons']),
        'native_executed': False, 'legal_verdict_claimed': False}
    RESULT.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
