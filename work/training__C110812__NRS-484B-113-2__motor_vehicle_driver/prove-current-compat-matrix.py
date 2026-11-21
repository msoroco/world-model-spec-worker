"""Regenerate eight exact current-runtime offline and compatibility proofs."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'draft-execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_one(case, suffix, candidate):
    stem = f'current-json-{suffix}-{candidate}'
    base = ROOT / '.runtime-work' / ('c110812-' + stem)
    if base.exists():
        raise ValueError('Fresh compatibility output required: ' + str(base))
    offline = base / 'offline'
    compatible = base / 'compatible'
    offline.parent.mkdir(parents=True)
    cli = [sys.executable, str(ROOT / 'runtime.py')]
    common = ['--manifest', str(MANIFEST), '--case', case,
              '--candidate', candidate]
    command = cli + ['offline'] + common + ['--output', str(offline)]
    offline_log = HERE / (stem + '-offline.log')
    with offline_log.open('w') as out:
        status = subprocess.run(command, cwd=ROOT, stdout=out, stderr=subprocess.STDOUT).returncode
    if status:
        raise RuntimeError(f'Offline failed {suffix}/{candidate}: {offline_log}')
    command = cli + ['compatibility'] + common + [
        '--output', str(compatible),
        '--library', str(ROOT / 'runtime/pipeline/library'),
        '--validator', str(ROOT / '.runtime-work/c110812-current-decoder/.lake/build/bin/adapterCheck')]
    compatibility_log = HERE / (stem + '-compatibility.log')
    with compatibility_log.open('w') as out:
        status = subprocess.run(command, cwd=ROOT, stdout=out, stderr=subprocess.STDOUT).returncode
    if status:
        raise RuntimeError(f'Compatibility failed {suffix}/{candidate}: {compatibility_log}')
    receipt = compatible / 'compatibility.json'
    proof = json.loads(receipt.read_text())
    if not proof['passed'] or proof['fixture_recipe_sha256'] != sha(HERE / f'diagnostic-condition_{"a" if suffix == "false" else "b"}-recipe.json'):
        raise ValueError('Compatibility output not bound to current fixture recipe')
    saved = HERE / (stem + '-receipt.json')
    shutil.copyfile(receipt, saved)
    negative = HERE / (stem + '-negative.log')
    shutil.copyfile(compatible / 'negative-analysis.log', negative)
    return {'case_id': case, 'candidate_id': candidate,
            'offline_log': offline_log.name, 'offline_log_sha256': sha(offline_log),
            'compatibility_log': compatibility_log.name,
            'compatibility_log_sha256': sha(compatibility_log),
            'receipt': saved.name, 'receipt_sha256': sha(saved),
            'negative_log': negative.name, 'negative_log_sha256': sha(negative),
            'analysis_log_sha256': proof['log_sha256'],
            'fixture_recipe_sha256': proof['fixture_recipe_sha256']}


def main():
    entries = json.loads(MANIFEST.read_text())['cases']
    rows = []
    for entry in entries:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            row = run_one(entry['case_id'], suffix, candidate)
            rows.append(row)
            print(suffix, candidate, 'passed', flush=True)
    (HERE / 'current-json-compat-summary.json').write_text(
        json.dumps({'format': 'c110812-current-json-matrix', 'rows': rows}, indent=2) + '\n')


if __name__ == '__main__':
    main()
