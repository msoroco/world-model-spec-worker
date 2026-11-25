"""Attempt exact scoped strict gate; restore partial automatically on failure."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
RESULT = FOLDER / 'result.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(value):
    RESULT.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    original = json.loads(RESULT.read_text())
    proposed = dict(original)
    proposed.update(status='ready', readiness_kind='delivery_prepared',
                    reason='Exact selected CPU package passed; original Native highway, pixels, physical outcome and legal interpretation remain delivery reviews.',
                    planned_case_count=3, candidate_count=6,
                    selected_delivery_case_count=3, cases_selected=3,
                    candidate_plans_proven=6, carla_executed=False, recordings_accepted=0,
                    first_gpu_delivery_command=(
                        f'python runtime.py execute-delivery --assignment {FOLDER.name} '
                        f'--case {FOLDER.name}__probe_01 --job "$JOB_ID" --db "$DB" '
                        '--run "$RUN" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"'),
                    tests=[{'command':
                        f'PYTHONDONTWRITEBYTECODE=1 TMPDIR=$PWD/.runtime-work PYTHONPATH=$PWD/work/{FOLDER.name}:$PWD/runtime/scenario_pipeline '
                        f'.venv-cpu/bin/python -m unittest discover -s work/{FOLDER.name}/tests -p test*.py -v',
                        'exit_code': 0, 'log': 'selected-root-tests.log',
                        'sha256': sha(FOLDER / 'selected-root-tests.log')}],
                    selected_delivery_proof={'offline_candidates': 6,
                        'compatibility_positive_negative': 6, 'saved_primary': 3,
                        'semantic_stages': 5, 'physical_fixtures': 9,
                        'delivery_positive_negative': 3,
                        'comparison_positive_negative': 1,
                        'original_native_observed': False})
    write(proposed)
    environment = dict(os.environ)
    environment.update(PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(ROOT / '.runtime-work'),
                       SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT / '.runtime-work/c111250-pipeline'))
    command = [sys.executable, 'worker_check.py', '--assignment', FOLDER.name,
               '--complete', '--require-delivery-ready']
    check = subprocess.run(command, cwd=ROOT, env=environment,
                           capture_output=True, text=True)
    (ROOT / '.runtime-work/c111250-strict.log').write_text(check.stdout + check.stderr)
    if check.returncode:
        original['strict_candidate_failure'] = check.stderr.strip().splitlines()[-1]
        original['reason'] = 'Selected CPU proofs assembled; exact scoped strict gate failed and needs repair.'
        write(original)
    print(json.dumps({'exit_code': check.returncode,
                      'last_line': (check.stdout + check.stderr).strip().splitlines()[-1]
                      if (check.stdout + check.stderr).strip() else ''}))
    return check.returncode


if __name__ == '__main__':
    raise SystemExit(main())
