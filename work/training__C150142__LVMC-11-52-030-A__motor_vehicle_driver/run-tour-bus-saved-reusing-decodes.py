"""Run pinned saved processing, reusing only verified exact-file decode receipts."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.media import verify_receipt

CASE = ROOT.name + '__tour_bus_below'
MANIFEST = ROOT / 'execution-manifest-diagnostic-tour_bus_below-draft.json'
VALIDATOR = REPO / '.runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck'
PRIOR = REPO / '.runtime-work/c150142-tour-bus-pinned-saved-below-result-v3/v0001'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def run(attempt, output):
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    private = REPO / '.runtime-work'
    if private not in attempt.parents or private not in output.parents or output.exists():
        raise ValueError('Use fresh ignored diagnostic paths')
    prior_result = json.loads((PRIOR / 'analysis/result.json').read_text())
    prior_receipts = {}
    mapping_sha = sha(attempt / 'video_frames.jsonl')
    for index, view in enumerate(prior_result['video_references']):
        verify_receipt(attempt / view, PRIOR / f'source-{index}.json', 36120,
                       mapping_sha256=mapping_sha)
        prior_receipts[view] = PRIOR / f'source-{index}.json'
    env = dict(os.environ, PYTHONHASHSEED='0')
    order = json.loads(subprocess.check_output([
        str(REPO / '.venv-cpu/bin/python'), '-c',
        'import json, measure_red_curb; print(json.dumps([v+".mkv" for v in measure_red_curb.VIEWS]))'],
        cwd=attempt, env=env, text=True))
    if set(order) != set(prior_receipts):
        raise ValueError('Pinned finalizer camera inventory differs')
    command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
               'process-saved', '--manifest', str(MANIFEST), '--case', CASE,
               '--attempt', str(attempt), '--output', str(output),
               '--library', str(REPO / 'runtime/pipeline/library'),
               '--validator', str(VALIDATOR)]
    run_label = output.name.rsplit('-', 1)[-1]
    if not run_label.startswith('v') or not run_label[1:].isdigit():
        raise ValueError('Output name needs a distinct version suffix')
    log = ROOT / ('update029-tour-bus-below-pinned-saved-' + run_label + '.log')
    if log.exists():
        raise ValueError('Retain prior pinned processing log')
    output.mkdir()
    with log.open('w') as stream:
        process = subprocess.Popen(command, cwd=REPO, stdout=stream,
                                   stderr=subprocess.STDOUT, env=env)
        version = output / 'v0001'
        for _ in range(1200):
            if version.is_dir():
                break
            if process.poll() is not None:
                raise RuntimeError('Pinned processing exited before output version')
            time.sleep(.1)
        else:
            process.terminate()
            raise TimeoutError('Pinned processing did not create an output version')
        for index, view in enumerate(order):
            shutil.copy2(prior_receipts[view],
                         version / f'source-{index}.json')
        status = process.wait()
    return {'case_id': CASE, 'process_exit_code': status,
            'reused_verified_complete_decodes': len(order),
            'camera_order': order,
            'log': str(log), 'output': str(version),
            'original_native_observed': False}


if __name__ == '__main__':
    value = run(sys.argv[1], sys.argv[2])
    print(json.dumps(value, sort_keys=True))
    if value['process_exit_code']:
        raise SystemExit(value['process_exit_code'])
