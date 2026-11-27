"""Run saved-only diagnostic replay for each primary selected construction."""
import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]
ROOT = FOLDER.parents[1]
VALIDATOR = ROOT / '.runtime-work/c229597-library-current/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def one(case):
    suffix = case.removeprefix(FOLDER.name + '__')
    scratch = ROOT / '.runtime-work' / ('c394566-saved-v17-' + suffix)
    command = [str(ROOT / '.venv-cpu/bin/python'), '-B', str(FOLDER / 'native/prove_saved.py'),
               '--case', case, '--scratch', str(scratch), '--library', str(ROOT / 'runtime/library'),
               '--validator', str(VALIDATOR)]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(ROOT / '.runtime-work'),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(scratch))
    result = subprocess.run(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, timeout=600)
    if result.returncode:
        raise ValueError('Saved-only failed for ' + suffix + ': ' + result.stdout[-1500:])
    original = scratch / 'saved'
    versions = list(original.glob('*/processing.json'))
    if len(versions) != 1:
        raise ValueError('Expected one saved version for ' + suffix)
    target = FOLDER / 'saved' / (suffix + '-processing.json')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(versions[0], target)
    log = FOLDER / 'saved' / (suffix + '-saved.log')
    log.write_text(result.stdout.rstrip() + '\n')
    return case, {'processing_receipt': str(target.relative_to(FOLDER)),
                  'processing_receipt_sha256': sha(target), 'test_log': str(log.relative_to(FOLDER)),
                  'test_log_sha256': sha(log)}


def main():
    manifest = json.loads((FOLDER / 'execution-probe-manifest.json').read_text())
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(one, [entry['case_id'] for entry in manifest['cases']]))
    proofs = dict(results)
    (FOLDER / 'saved/proof-index.json').write_text(json.dumps(proofs, indent=2) + '\n')
    print(json.dumps({'saved_only_cases': len(results)}))


if __name__ == '__main__':
    main()
