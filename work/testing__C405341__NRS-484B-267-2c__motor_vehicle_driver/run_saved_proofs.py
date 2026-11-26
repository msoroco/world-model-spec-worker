"""Replay each selected diagnostic attempt through recorded-only processing."""
import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c405341'
VALIDATOR = ROOT / '.runtime-work/c233829/decoder/.lake/build/bin/adapterCheck'


def run(entry):
    case = entry['case_id']
    name = case.removeprefix(HERE.name + '__')
    attempt = next(
        (candidate for candidate in (
            SCRATCH / ('compat-' + name + '-v5'),)
         if (candidate / 'compatibility.json').is_file() and
         json.loads((candidate / 'compatibility.json').read_text()).get('construction_sha256') == entry['construction_sha256']),
        None)
    if attempt is None:
        return name, 1, 'current compatibility attempt missing'
    replay_attempt = SCRATCH / ('saved-input-emergency-' + name)
    if not replay_attempt.exists():
        shutil.copytree(attempt, replay_attempt, copy_function=os.link)
        (replay_attempt / 'candidate-selection.json').unlink(missing_ok=True)
    output = SCRATCH / ('saved-emergency-' + name)
    for prior in sorted(output.glob('v*/processing.json'), reverse=True):
        receipt = json.loads(prior.read_text())
        if (receipt.get('passed') is True and receipt.get('recorded_only') is True and
                receipt.get('native_revision', {}).get('construction_sha256') == entry['construction_sha256']):
            return name, 0, 'passed prior recorded-only replay'
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / ('pipeline-saved-' + name)))
    command = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
               'process-saved', '--manifest', str(HERE / 'execution-manifest.json'),
               '--case', case, '--attempt', str(replay_attempt), '--output', str(output),
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
