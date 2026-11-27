"""Attempt exact scoped strict gate; restore partial status on any failure."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'result.json'
    original = json.loads(path.read_text())
    if original['assignment_id'] != AID or original['applied_update'] != 16:
        raise ValueError('Frozen assignment identity or update differs')
    if original['status'] not in ('partial', 'ready'):
        raise ValueError('Unexpected readiness status')
    log = HERE / 'proofs/cpu-tests.log'
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    ready = dict(original)
    ready.update(status='ready', reason=None, readiness_kind='delivery_prepared',
        cases_planned=len(plan['cases']), cases_selected=len(manifest['cases']),
        candidate_plans_proven=sum(1 + len(row['candidates']) for row in manifest['cases']),
        comparison_audits_passed=len(plan['comparisons']), carla_executed=False,
        recordings_accepted=0, cpu_diagnostic_proof='native/double-parking-proof.log',
        tests=[{'command': "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$PWD .venv-cpu/bin/python -B -m unittest discover -s work/" + AID + "/tests -p 'test*.py' -v",
                'exit_code': 0, 'log': 'proofs/cpu-tests.log', 'sha256': digest(log)}],
        remaining_gpu_checks=[
            'Original CARLA two-vehicle highway-side geometry and four-camera source capture',
            'Independent highway/curb authority, actual stop/stand/park purpose, traffic necessity, applicable law, officer and official device direction review',
            'Original physical completion, actual pixels, full decode and legal outcome require independent local review'],
        first_gpu_delivery_command=(
            'PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python -m worker_exchange '
            'execute-delivery --repo . --batch full-train-delivery --db $DB --assignment ' + AID +
            ' --case ' + manifest['cases'][0]['case_id'] +
            ' --run $RUN --job $JOB_ID --python $CARLA_PYTHON --host $CARLA_HOST --port $CARLA_PORT'))
    path.write_text(json.dumps(ready, indent=2, ensure_ascii=False) + '\n')
    command = [sys.executable, str(ROOT / 'worker_check.py'), '--assignment', AID,
               '--complete', '--require-delivery-ready']
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    strict_log = ROOT / '.runtime-work/c229398-strict.log'
    strict_log.write_text(result.stdout + result.stderr)
    if result.returncode:
        partial = dict(original)
        partial.update(status='partial', readiness_kind='implementation_checkpoint',
            reason='Exact scoped strict gate failed; see .runtime-work/c229398-strict.log')
        path.write_text(json.dumps(partial, indent=2, ensure_ascii=False) + '\n')
        print(result.stderr[-2500:] or result.stdout[-2500:])
        raise SystemExit(result.returncode)
    print('Exact scoped strict gate passed; log_sha256=' + digest(strict_log))


if __name__ == '__main__':
    main()
