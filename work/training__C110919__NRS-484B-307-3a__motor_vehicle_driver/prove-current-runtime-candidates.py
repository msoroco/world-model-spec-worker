"""Run exact offline and public compatibility checks on current source bytes."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'current-v2-probe-manifest.json'
SCRATCH = ROOT / '.runtime-work/c110919-3a-owner/matrix'
VALIDATOR = ROOT / '.runtime-work/c110919-owner104/decoder/.lake/build/bin/adapterCheck'
CASES = [('witness_1', 'primary'), ('witness_2', 'primary'),
         ('witness_1', 'fallback1'), ('witness_2', 'fallback1'),
         ('witness_1', 'fallback3'), ('witness_2', 'fallback3')]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def run_one(case, candidate):
    case_id = HERE.name + '__' + case
    name = case + '-' + candidate
    output = SCRATCH / name
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(ROOT / '.runtime-work'),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH))
    args = ['--manifest', str(MANIFEST), '--case', case_id, '--candidate', candidate]
    offline = output / 'offline'
    offline.parent.mkdir(parents=True, exist_ok=True)
    first = subprocess.run([sys.executable, str(ROOT / 'runtime.py'), 'offline', *args,
                            '--output', str(offline)], cwd=ROOT, env=env,
                           capture_output=True, text=True, timeout=300)
    if first.returncode:
        raise ValueError(name + ' offline: ' + first.stderr[-2000:])
    compat = output / 'compatibility'
    second = subprocess.run([sys.executable, str(ROOT / 'runtime.py'), 'compatibility', *args,
                             '--output', str(compat), '--library', str(ROOT / 'runtime/library'),
                             '--validator', str(VALIDATOR)], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=900)
    if second.returncode:
        raise ValueError(name + ' compatibility: ' + second.stderr[-2000:])
    receipt = json.loads((compat / 'compatibility.json').read_text())
    if not receipt['passed'] or receipt['runtime_manifest_sha256'] != sha(ROOT / 'runtime/SOURCE-MANIFEST.json'):
        raise ValueError(name + ' receipt does not bind current runtime')
    destination = HERE / 'current-runtime-proofs' / case / candidate
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'offline.log').write_text(first.stdout.rstrip() + '\n')
    for source, name_out in [('compatibility.json', 'compatibility.json'),
                             ('compatibility-analysis.log', 'analysis.log'),
                             ('negative-analysis.log', 'negative-analysis.log')]:
        shutil.copyfile(compat / source, destination / name_out)
    return {'case_id': case_id, 'candidate': candidate,
            'construction_sha256': receipt['construction_sha256'],
            'receipt_sha256': sha(destination / 'compatibility.json'),
            'offline_log_sha256': sha(destination / 'offline.log'),
            'analysis_log_sha256': sha(destination / 'analysis.log'),
            'negative_log_sha256': sha(destination / 'negative-analysis.log'),
            'checks': receipt['checks']}


if __name__ == '__main__':
    if not VALIDATOR.is_file():
        raise ValueError('Current Lean decoder is missing')
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(run_one, *pair): pair for pair in CASES}
        results = []
        for future in concurrent.futures.as_completed(futures):
            value = future.result()
            print(value['case_id'].split('__')[-1], value['candidate'], 'passed', flush=True)
            results.append(value)
    write(HERE / 'current-runtime-candidate-matrix.json',
          {'format': 'c110919-3a-current-runtime-candidate-matrix', 'passed': True,
           'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
           'cases': sorted(results, key=lambda row: (row['case_id'], row['candidate']))})
