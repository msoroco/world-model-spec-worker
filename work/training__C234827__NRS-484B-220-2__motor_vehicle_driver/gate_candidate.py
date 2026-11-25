"""Run exact scoped strict gate and restore truthful partial status on failure."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
RESULT = HERE / 'result.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    prior = json.loads(RESULT.read_text())
    current = dict(prior)
    command = ('PYTHONDONTWRITEBYTECODE=1 TMPDIR=$PWD/.runtime-work/c234827-nrs-tmp '
               'MPLCONFIGDIR=$PWD/.runtime-work/c234827-nrs-mpl '
               '.venv-cpu/bin/python worker_check.py --assignment ' + AID +
               ' --complete --require-delivery-ready')
    current.update(status='ready', readiness_kind='delivery_prepared',
                   reason='Selected delivery package passed exact scoped CPU strict gate; original physical and legal review remain pending.',
                   first_gpu_delivery_command=('python runtime.py execute-delivery --assignment ' + AID +
                       ' --case ' + AID + '__reference --job "$JOB_ID" --db "$DB" --run "$RUN" '
                       '--python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"'),
                   tests=[{'command': 'PYTHONDONTWRITEBYTECODE=1 TMPDIR=$PWD/.runtime-work/c234827-nrs-tmp '
                                      'PYTHONPATH=$PWD/work/' + AID + ':$PWD/runtime/scenario_pipeline '
                                      '.venv-cpu/bin/python -m unittest discover -s work/' + AID +
                                      '/tests -p test*.py -v',
                           'exit_code': 0, 'log': 'selected-root-tests.log',
                           'sha256': sha(HERE / 'selected-root-tests.log')}],
                   selected_delivery_proof={'offline_candidates': 4,
                                            'compatibility_positive_negative': 4,
                                            'saved_primary': 2, 'semantic_stages': 5,
                                            'physical_fixtures': 6,
                                            'delivery_positive_negative': 2,
                                            'paired_comparison_positive_negative': 1,
                                            'original_native_observed': False})
    RESULT.write_text(json.dumps(current, indent=2) + '\n')
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE='1',
               TMPDIR=str(REPO / '.runtime-work/c234827-nrs-tmp'),
               MPLCONFIGDIR=str(REPO / '.runtime-work/c234827-nrs-mpl'),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / '.runtime-work/c234827-nrs-pipeline'))
    check = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'worker_check.py'),
             '--assignment', AID, '--complete', '--require-delivery-ready']
    process = subprocess.run(check, cwd=REPO, env=env, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log = HERE / 'current-scoped-strict.log'
    log.write_text(process.stdout.rstrip() + '\n')
    if process.returncode:
        prior['reason'] = ('Selected public/saved and independent CPU proofs built; current scoped strict '
                           'gate still fails. See current-scoped-strict.log for exact remaining contract gap.')
        RESULT.write_text(json.dumps(prior, indent=2) + '\n')
    print(json.dumps({'command': command, 'exit_code': process.returncode,
                      'log': str(log.relative_to(REPO)),
                      'tail': process.stdout.strip().splitlines()[-6:]}))
    return process.returncode


if __name__ == '__main__':
    sys.exit(main())
