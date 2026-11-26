"""Replay each selected diagnostic attempt through recorded-only processing."""
import concurrent.futures
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c179789-new'
VALIDATOR = ROOT / '.runtime-work/c179789-decoder/.lake/build/bin/adapterCheck'


def run(entry):
    case = entry['case_id']
    name = case.removeprefix(HERE.name + '__')
    attempt = SCRATCH / ('compat-' + name + '-final')
    output = SCRATCH / ('saved-' + name)
    prior = output / 'v0001/processing.json'
    if prior.is_file():
        receipt = json.loads(prior.read_text())
        if (receipt.get('passed') is True and receipt.get('recorded_only') is True and
                receipt.get('native_revision', {}).get('construction_sha256') == entry['construction_sha256']):
            return name, 0, 'passed prior v0001'
    selection = attempt / 'candidate-selection.json'
    if selection.exists():
        selection.unlink()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / ('pipeline-saved-' + name)))
    command = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
               'process-saved', '--manifest', str(HERE / 'execution-manifest.json'),
               '--case', case, '--attempt', str(attempt), '--output', str(output),
               '--library', str(ROOT / 'runtime/library'), '--validator', str(VALIDATOR)]
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    (SCRATCH / ('saved-command-' + name + '.log')).write_text(
        (result.stdout if result.returncode == 0 else result.stderr[-4000:]).rstrip() + '\n')
    return name, result.returncode, 'passed' if result.returncode == 0 else result.stderr[-400:]


def main():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    failed = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for future in concurrent.futures.as_completed(
                [pool.submit(run, entry) for entry in manifest['cases']]):
            outcome = future.result()
            print(outcome, flush=True)
            if outcome[1]:
                failed.append(outcome[0])
    if failed:
        raise ValueError('recorded-only replay failed: ' + ', '.join(failed))


if __name__ == '__main__':
    main()
