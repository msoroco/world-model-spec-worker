"""Author exact-case canonical delivery commands for shared queue adoption."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
PREFIX = f'PYTHONPATH={ROOT}/runtime/pipeline {ROOT}/.venv-cpu/bin/python -m scenario_pipeline.worker_exchange'
BASE = f'--repo {ROOT} --batch {ROOT}/batch.json --db "$DB"'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = json.loads(MANIFEST.read_text())
rows = []
for entry in manifest['cases']:
    case = entry['case_id']
    common = f'{BASE} --assignment {HERE.name} --case {case}'
    prepare = f'{PREFIX} prepare-delivery {common} --candidate primary'
    execute = (f'{PREFIX} execute-delivery {common} --run "$RUN" --job "$JOB_ID" '
               '--python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"')
    accept = (f'{PREFIX} accept-delivery {common} --run "$RUN" --job "$JOB_ID" '
              '--attempt "$ATTEMPT_ID" --audit "$AUDIT_JSON"')
    rows.append({'assignment_id': HERE.name, 'case_id': case,
                 'prepare_command': prepare, 'execute_command': execute,
                 'accept_command': accept,
                 'candidate_commands': {c['id']: f'{PREFIX} prepare-delivery {common} --candidate {c["id"]}'
                                        for c in entry['candidates']},
                 'postprocessing_command': entry['post_capture']['command'],
                 'owner_release_command': 'wait "$NATIVE_PID"; test "$OWNER_RELEASED" = true',
                 'additional_source_audit_command':
                    f'{ROOT}/.venv-cpu/bin/python {HERE}/delivery_audit.py --case {case} '
                    '--candidate "$CANDIDATE_ID" --attempt "$SAVED_ATTEMPT" '
                    '--processing "$PROCESSED_OUT/v0001/processing.json" --output "$AUDIT_JSON"',
                 'capture_command': execute})
comparisons = json.loads((HERE / 'comparison-audit-specs.json').read_text())['comparisons']
comparison_rows = [{'assignment_id': HERE.name, 'comparison_id': c['comparison_id'],
                    'command': f'{ROOT}/.venv-cpu/bin/python {HERE}/comparison_audit.py '
                    f'--comparison {c["comparison_id"]} --left "$LEFT_ATTEMPT" '
                    '--right "$RIGHT_ATTEMPT" --output "$COMPARISON_AUDIT_JSON"'}
                   for c in comparisons]
value = {'format': 'c111256-exact-delivery-commands', 'manifest_sha256': sha(MANIFEST),
         'cases': rows, 'comparison_audit_commands': comparison_rows,
         'scope': 'Portable command template; GPU/DB execution and acceptance not attempted'}
(HERE / 'dispatch-commands.json').write_text(json.dumps(value, indent=2) + '\n')
result_path = HERE / 'result.json'
result = json.loads(result_path.read_text())
result['first_gpu_delivery_command'] = rows[0]['execute_command']
result_path.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'cases': len(rows), 'comparisons': len(comparison_rows),
                  'manifest_sha256': value['manifest_sha256']}))
