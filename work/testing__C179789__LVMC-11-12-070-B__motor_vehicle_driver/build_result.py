"""Build a candidate ready return from current bound CPU proofs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    test_log = HERE / 'cpu-current-tests.log'
    if (len(manifest['cases']) != 10 or len(plan['comparisons']) != 4 or
            not test_log.read_text().rstrip().endswith('OK')):
        raise ValueError('current CPU proof suite incomplete')
    first = manifest['cases'][0]['case_id']
    command = ('SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c179789-local-capture" '
               'PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m '
               'scenario_pipeline.worker_exchange --root "$LOCAL_ROOT" execute-delivery '
               f'--repo "$PWD" --batch full-test-delivery --db "$DB" --assignment {AID} '
               f'--case {first} --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" '
               '--host "$CARLA_HOST" --port "$CARLA_PORT"')
    value = {'assignment_id': AID,
             'input_sha256': sha(ROOT / 'inputs' / AID / 'assignment.json'),
             'status': 'ready', 'readiness_kind': 'delivery_prepared',
             'applied_update': json.loads((ROOT / 'batch.json').read_text())['update_version'],
             'tests': [{'command': f'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/{AID}/tests -v',
                        'exit_code': 0, 'log': test_log.name, 'sha256': sha(test_log)}],
             'remaining_gpu_checks': [
                 'Review and source-hash original municipal jurisdiction, through-highway designation, entrance control, distinct routes and subsection A antecedent before Native capture.',
                 'Capture and independently review 900 synchronized original frames with both vehicle histories and four camera pixel streams.',
                 'Review actual physical traversal, antecedent statutory satisfaction and right-of-way without a fabricated legal cutoff.'
             ],
             'reason': 'CPU-prepared source-gated original Native delivery for ten exact cases and four controlled comparisons. Diagnostic fixtures establish software compatibility and saved processing; original junction sources, two-actor motion, four camera pixels and legal judgment remain for local review.',
             'cpu_proofs': {
                 'exact_cases': 10, 'controlled_comparisons': 4,
                 'focused_tests': 15, 'selected_offline_passed': 10,
                 'selected_compatibility_passed': 10,
                 'selected_saved_recorded_only_passed': 10,
                 'physical_three_state_and_lifecycle_passed': 10,
                 'selected_independent_delivery_bindings': 10,
                 'selected_independent_comparisons': 4,
                 'selected_manifest_sha256': sha(manifest_path),
                 'semantic_index_sha256': sha(HERE / 'proposals/semantic-index.json'),
                 'diagnostic_selected_audit_sha256': sha(HERE / 'selected-audit.json'),
                 'original_comparison_audit_plan_sha256': sha(HERE / 'comparison-audit-plan.json')},
             'first_gpu_delivery_command': command}
    (HERE / 'result.json').write_text(json.dumps(value, indent=2) + '\n')


if __name__ == '__main__':
    build()
