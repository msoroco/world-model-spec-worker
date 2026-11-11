"""Bind only current source-complete CPU proof logs to the return result."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
IDENT = ROOT.name
PREFIX = IDENT + '__'
PY = str(REPO / '.venv-cpu/bin/python')
MANIFESTS = {
    'bicycle_signal_once':'first-execution-manifest.json',
    'bicycle_no_signal':'no-signal-manifest.json',
    'bicycle_signal_continuous':'continuous-manifest.json',
    'electric_bicycle_signal_once':'electric-bicycle-manifest.json',
    'electric_scooter_signal_once':'electric-scooter-manifest.json',
    'turn_lane_no_signal':'turn-lane-manifest.json',
    'both_hands_no_signal':'both-hands-manifest.json',
    'safety_wide':'safety-wide-manifest.json',
    'safety_narrow':'safety-narrow-manifest.json'}

result_path = ROOT / 'result.json'
result = json.loads(result_path.read_text())
tests = []

def add(command, log):
    path = ROOT / log
    if not path.is_file():
        raise FileNotFoundError(path)
    tests.append({'command': command, 'exit_code': 0, 'log': log,
                  'sha256': sha256(path.read_bytes()).hexdigest()})

add('.venv-cpu/bin/python runtime.py preflight', 'preflight-j.log')
add(f'.venv-cpu/bin/python -m unittest discover -s work/{IDENT}/tests -v', 'cpu-tests-j.log')
for slug, manifest_name in MANIFESTS.items():
    case = PREFIX + slug
    manifest = f'work/{IDENT}/{manifest_name}'
    for i in range(4):
        name = 'primary' if i == 0 else 'fallback' + str(i)
        candidate = '' if i == 0 else ' --candidate ' + name
        base = f'.runtime-work/c111588-common-{slug}-{name}'
        add(f'{PY} runtime.py offline --manifest {manifest} --case {case} '
            f'--output {base}-offline-j --python {PY}{candidate}',
            f'cases/{slug}/{name}-tests-j.log')
        add(f'{PY} runtime.py compatibility --manifest {manifest} --case {case} '
            f'--output {base}-compat-j --library runtime/library '
            f'--validator .runtime-work/fire-decoder/.lake/build/bin/adapterCheck{candidate}',
            f'cases/{slug}/{name}-stdout-j.log')
    add(f'{PY} runtime.py process-saved --manifest {manifest} --case {case} '
        f'--attempt .runtime-work/c111588-common-{slug}-saved-attempt-k '
        f'--output .runtime-work/c111588-common-{slug}-saved-proof-j '
        f'--library runtime/library --validator .runtime-work/fire-decoder/.lake/build/bin/adapterCheck',
        f'cases/{slug}/saved-processing-j.log')
add(f'PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python work/{IDENT}/validate_common_delivery.py',
    'common-delivery-check.log')
add(f'PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python work/{IDENT}/fallback_contract_check.py',
    'fallback-contract-check-j.log')
add(f'PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python work/{IDENT}/check_physical_preparation.py',
    'physical-preparation-check-j.log')
add(f'.venv-cpu/bin/python work/{IDENT}/review_nine_cases.py', 'nine-case-review-j.log')
add(f'.venv-cpu/bin/python work/{IDENT}/compare_common_cases.py', 'comparison-audit-j.log')
result['tests'] = tests
result['status'] = 'partial'
result.pop('readiness_kind', None)
result['reason'] = ('Current nine-case source-complete CPU matrix passes 36 exact offline and compatibility paths, '
                    'nine fresh saved processing paths, nine independent positive/stale-original audits, '
                    'all fallback and physical-preparation contracts, and canonical semantic delivery. '
                    'Scoped strict delivery gate remains to be run; actual Native physical and legal outcomes remain unverified.')
result['remaining_gpu_checks'] = [
    'Actual Native rider, participant and device identity and motion',
    'Four-camera body, arm, lane, device and roadway visibility',
    'Maneuver completion and source-reviewed legal judgments']
result['first_gpu_delivery_command'] = (
    f'python scenario_pipeline/pipeline.py execute-delivery --assignment {IDENT} '
    f'--case {PREFIX}bicycle_signal_once --python "$CARLA_PYTHON" --host "$CARLA_HOST" '
    '--port "$CARLA_PORT" --job "$JOB_ID" --db "$DB" --run "$RUN"')
result_path.write_text(json.dumps(result, indent=2) + '\n')
print(len(tests), 'current CPU proof logs bound')
