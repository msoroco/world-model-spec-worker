"""Reprocess selected synthetic acquisitions with current manifest and analyzer."""
import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[1]
MANIFEST = PACKAGE / 'execution-manifest.json'
VALIDATOR = ROOT / '.runtime-work/c229597-library-current/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(case_id):
    suffix = case_id.rsplit('__', 1)[-1]
    category = 'sweep' if suffix.startswith('judgment-') else 'selected'
    attempt = ROOT / '.runtime-work' / ('c229597-' + category + '-compat-' + suffix + '-primary-v5'
                                      if category == 'sweep' else 'c229597-selected-' + suffix + '-primary-current-v2')
    if not attempt.is_dir():
        raise ValueError('Missing current exact diagnostic acquisition: ' + suffix)
    selection = ROOT / '.runtime-work' / ('c229597-current-selection-' + suffix)
    materialize = [sys.executable, str(ROOT / 'runtime.py'), 'materialize',
                   '--manifest', str(MANIFEST), '--case', case_id,
                   '--candidate', 'primary', '--output', str(selection)]
    env = dict(os.environ, TMPDIR=str(ROOT / '.runtime-work'), PYTHONDONTWRITEBYTECODE='1')
    subprocess.run(materialize, cwd=ROOT, env=env, check=True, capture_output=True, text=True)
    shutil.copyfile(selection / 'candidate-selection.json', attempt / 'candidate-selection.json')
    output = ROOT / '.runtime-work' / ('c229597-current-saved-' + suffix)
    command = [sys.executable, str(ROOT / 'runtime.py'), 'process-saved',
               '--manifest', str(MANIFEST), '--case', case_id,
               '--attempt', str(attempt), '--output', str(output),
               '--library', str(ROOT / 'runtime/library'), '--validator', str(VALIDATOR)]
    command_log = ROOT / '.runtime-work' / ('c229597-current-saved-' + suffix + '.log')
    with command_log.open('w') as stream:
        process = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
    if process.returncode:
        raise RuntimeError(f'{suffix}: saved processing exit {process.returncode}; {command_log}')
    receipt = json.loads((output / 'v0001/processing.json').read_text())
    if (receipt.get('passed') is not True or receipt.get('case_id') != case_id
            or receipt.get('missing_evidence') or not receipt.get('recorded_only')
            or not receipt.get('originals_preserved') or not receipt['final_video_checks']['passed']):
        raise ValueError('Incomplete saved receipt: ' + suffix)
    dest = PACKAGE / ('sweep-cases/' + case_id + '/saved' if category == 'sweep'
                      else 'selected-saved-proofs/' + suffix)
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(output / 'v0001/processing.json', dest / 'processing.json')
    shutil.copyfile(output / 'v0001/processing.json', dest / 'process-saved.log')
    rel = str(dest.relative_to(PACKAGE))
    return case_id, {'receipt': rel + '/processing.json',
                     'sha256': sha(dest / 'processing.json'),
                     'log': rel + '/process-saved.log',
                     'log_sha256': sha(dest / 'process-saved.log')}


def main():
    manifest = json.loads(MANIFEST.read_text())
    jobs = [entry['case_id'] for entry in manifest['cases']]
    if len(jobs) != 8:
        raise ValueError('Expected eight saved processing jobs')
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(run, case_id): case_id for case_id in jobs}
        for future in concurrent.futures.as_completed(futures):
            case_id, spec = future.result()
            entry = next(item for item in manifest['cases'] if item['case_id'] == case_id)
            entry['saved_processing'] = spec
            print(case_id, 'saved processing passed', flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
