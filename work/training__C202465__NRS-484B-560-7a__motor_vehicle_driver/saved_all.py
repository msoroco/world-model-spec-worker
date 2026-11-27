"""Exercise recorded-only processing on the synthetic public source snapshots."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VARIANTS = ('space_clear', 'space_short', 'grade_clear', 'grade_deficit',
            'trailing_exact', 'trailing_just_short')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(suffix):
    if suffix not in VARIANTS:
        raise ValueError('Exact selected rail case required')
    manifest = HERE / 'execution-manifest.json'
    base = ROOT / '.runtime-work' / ('c202465-saved-' + sha(manifest)[:12])
    public = ROOT / '.runtime-work' / ('c202465-public-' + sha(manifest)[:12]) / (suffix + '-primary')
    if not (public / 'compatibility.json').is_file():
        raise ValueError('Public positive and negative checks must pass first')
    attempt = base / (suffix + '-attempt')
    output = base / (suffix + '-output')
    if attempt.exists() or output.exists():
        raise ValueError('Retain prior saved attempt; choose a fresh proof revision')
    base.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(ROOT / '.runtime-work'),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT / '.runtime-work/c202465'),
               PYTHONPATH=str(ROOT / 'runtime/scenario_pipeline') + os.pathsep +
                          str(ROOT / 'runtime/python'))
    case = HERE.name + '__' + suffix
    prepare = [sys.executable, '-B', str(HERE / 'prepare_saved.py'),
               '--manifest', str(manifest), '--case', case,
               '--public', str(public), '--attempt', str(attempt)]
    staged = subprocess.run(prepare, cwd=ROOT, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if staged.returncode:
        raise RuntimeError('Saved source staging failed: ' + staged.stdout[-1500:])
    validator = ROOT / '.runtime-work/c179480/decoder/.lake/build/bin/adapterCheck'
    command = [sys.executable, '-B', str(ROOT / 'runtime.py'), 'process-saved',
               '--manifest', str(manifest), '--case', case,
               '--attempt', str(attempt), '--output', str(output),
               '--library', str(ROOT / 'runtime/library'), '--validator', str(validator)]
    process = subprocess.run(command, cwd=ROOT, env=env, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if process.returncode:
        raise RuntimeError('Recorded-only processing failed: ' + process.stdout[-2000:])
    version = output / 'v0001'
    receipt = json.loads((version / 'processing.json').read_text())
    if (receipt.get('passed') is not True or receipt.get('recorded_only') is not True or
            receipt.get('originals_preserved') is not True or receipt.get('missing_evidence')):
        raise ValueError('Recorded-only receipt incomplete')
    folder = HERE / 'proofs' / suffix
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / 'saved-processing.json'
    shutil.copyfile(version / 'processing.json', target)
    log = folder / 'saved-analysis.log'
    shutil.copyfile(version / 'analysis.log', log)
    for path in (target, log):
        content = path.read_bytes()
        if (len(content) > 2 * 1024 * 1024 or content.endswith(b'\n\n') or
                any(line.rstrip(b' \t\r') != line for line in content.splitlines())):
            raise ValueError('Returned saved proof size or whitespace differs')
    return {'case_id': case, 'recorded_only': True,
            'receipt_sha256': sha(target), 'analysis_log_sha256': sha(log)}


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: saved_all.py CASE_SUFFIX')
    print(json.dumps(run(sys.argv[1])))
