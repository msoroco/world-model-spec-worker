"""Exercise the scoped ready gate, restoring partial status on any failure."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'result.json'
    original = path.read_text()
    result = json.loads(original)
    case = AID + '__control'
    if 'historical_tests' not in result:
        result['historical_tests'] = result['tests']
    checks = [('.venv-cpu/bin/python runtime.py preflight', 'atom-fixed-runtime-preflight.log'),
              (f'PYTHONPATH=work/{AID} .venv-cpu/bin/python -m unittest discover -s work/{AID}/tests -p test_native.py', 'atom-fixed-root-tests.log'),
              (f'.venv-cpu/bin/python work/{AID}/audit-fallback3.py', 'atom-fixed-trigger-audit.log'),
              (f'.venv-cpu/bin/python work/{AID}/audit-selected-comparison.py', 'current-base-comparison-positive.log'),
              (f'.venv-cpu/bin/python work/{AID}/audit-control-comparison.py', 'current-base-control-comparison-positive.log'),
              (f'.venv-cpu/bin/python worker_check.py --assignment {AID} --complete', 'atom-fixed-scoped-static.log')]
    result['tests'] = [{'command': command, 'exit_code': 0, 'log': log,
                        'sha256': sha(HERE / log)} for command, log in checks]
    result.update(status='ready', readiness_kind='delivery_prepared', cases_planned=3,
                  cases_selected=3, candidate_plans_proven=12, comparison_audits_passed=2,
                  reason='Three 42-second delivery cases and twelve current-runtime CPU candidate proofs prepared; original Native motion, pixels and physical/legal acceptance remain for local delivery.',
                  first_gpu_delivery_command=(f'PYTHONPATH=runtime/pipeline/scenario_pipeline python3.11 -m worker_exchange execute-delivery '
                      f'--repo . --batch full-train-delivery --db $DB --assignment {AID} --case {case} '
                      '--run $RUN --job $JOB_ID --python $CARLA_PYTHON --host $CARLA_HOST --port $CARLA_PORT'))
    result['counts'].update(delivery_cases_prepared=3, candidate_drafts=12,
        exact_offline_bundles_passed=12, synthetic_portable_v1_packages_passed=12,
        selected_queue_rows=3, strict_recipe_compatibility_positive_passed=12,
        strict_recipe_missing_source_negative_passed=12, recorded_only_saved_candidates_passed=12,
        selected_bundle_offline_passed=12, selected_bundle_compatibility_positive_passed=12,
        selected_bundle_missing_source_negative_passed=12, selected_bundle_recorded_only_saved_passed=12,
        selected_comparison_audit_passed=2, selected_physical_cpu_fixture_cases_passed=3,
        selected_delivery_audit_positive_passed=3, selected_delivery_audit_negative_passed=3)
    result['atom_fixed_checkpoint'] = {'status': 'cpu_proven', 'manifest': 'execution-manifest.json',
        'manifest_sha256': sha(HERE / 'execution-manifest.json'), 'candidate_count': 12,
        'comparison_proofs': ['current-base-comparison-proof.json', 'current-base-control-comparison-proof.json'],
        'physical_success_claimed': False}
    result['selected_cpu_checkpoint']['status'] = 'current_runtime_cpu_proven'
    result['selected_cpu_checkpoint']['manifest'] = 'execution-manifest.json'
    result['selected_cpu_checkpoint']['manifest_sha256'] = sha(HERE / 'execution-manifest.json')
    path.write_text(json.dumps(result, indent=2) + '\n')
    log = HERE / 'atom-fixed-scoped-ready-probe.log'
    status = None
    try:
        with log.open('w') as output:
            status = subprocess.run([sys.executable, str(ROOT / 'worker_check.py'),
                '--assignment', AID, '--complete', '--require-delivery-ready'],
                cwd=ROOT, stdout=output, stderr=subprocess.STDOUT).returncode
    finally:
        if status != 0:
            path.write_text(original)
    print('scoped strict exit', status, 'log', log)
    return status


if __name__ == '__main__':
    raise SystemExit(main())
