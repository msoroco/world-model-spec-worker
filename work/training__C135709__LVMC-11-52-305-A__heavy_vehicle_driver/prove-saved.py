"""Exercise recorded-only processing on fresh synthetic source-shaped attempts."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'draft-execution-manifest.json'
DECODER = ROOT / '.runtime-work/nrs-decoder/.lake/build/bin/adapterCheck'


def run(tokens, log=None):
    result = subprocess.run(tokens, cwd=ROOT, capture_output=True, text=True,
                            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    if log is not None:
        log.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError('Failed: ' + ' '.join(tokens) + '\n' + result.stderr[-2000:])


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.split('__')[-1]
        fixture = ROOT / '.runtime-work' / ('c135709-v5-saved-fixture-' + suffix)
        attempt = ROOT / '.runtime-work' / ('c135709-v5-saved-attempt-' + suffix)
        output = ROOT / '.runtime-work' / ('c135709-v5-saved-' + suffix)
        run([sys.executable, str(ROOT / 'runtime.py'), 'fixture', '--recipe',
             str(HERE / ('diagnostic-' + suffix + '-recipe.json')), '--output', str(fixture)])
        run([sys.executable, str(ROOT / 'runtime.py'), 'materialize', '--manifest', str(MANIFEST),
             '--case', case, '--output', str(attempt)])
        for path in fixture.iterdir():
            target = attempt / path.name
            if target.exists():
                continue
            if path.is_dir():
                shutil.copytree(path, target)
            else:
                shutil.copy2(path, target)
        log = HERE / 'proofs' / suffix / 'saved.log'
        run([sys.executable, str(ROOT / 'runtime.py'), 'process-saved', '--manifest', str(MANIFEST),
             '--case', case, '--attempt', str(attempt), '--output', str(output),
             '--library', str(ROOT / 'runtime/library'), '--validator', str(DECODER)], log)
        processing = json.loads((output / 'v0001/processing.json').read_text())
        if not processing.get('passed') or processing.get('recorded_only') is not True:
            raise ValueError('Recorded-only proof did not pass: ' + case)
        print(suffix, 'recorded-only saved processing passed', flush=True)


if __name__ == '__main__':
    main()
