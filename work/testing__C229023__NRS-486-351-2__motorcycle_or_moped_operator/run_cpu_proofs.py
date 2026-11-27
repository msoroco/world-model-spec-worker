"""Run and bind exact-case primary and fallback CPU package proofs."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work/c229023-owner-nov26'
VALIDATOR = REPO / '.runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_manifest(manifest):
    (ROOT / 'execution-manifest.json').write_text(
        json.dumps(manifest, indent=2, allow_nan=False) + '\n')


def run(command, capture):
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE='1',
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),
               TMPDIR=str(SCRATCH), MPLCONFIGDIR=str(SCRATCH / 'mpl'))
    with capture.open('w') as output:
        process = subprocess.run(command, cwd=REPO, env=env, stdout=output,
                                 stderr=subprocess.STDOUT, text=True)
    if process.returncode:
        raise ValueError(f'{shlex.join(command)} failed; see {capture}')


def main():
    if not VALIDATOR.is_file():
        raise ValueError('Pinned local Native/Lean validator absent')
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.removeprefix(ROOT.name + '__')
        folder = ROOT / 'cases' / suffix
        folder.mkdir(parents=True, exist_ok=True)
        for candidate in ('primary', 'fallback1'):
            target = entry if candidate == 'primary' else entry['candidates'][0]
            key = 'primary' if candidate == 'primary' else 'fallback1'
            offline_output = SCRATCH / f'offline-{suffix}-{key}-proof'
            if offline_output.exists():
                shutil.rmtree(offline_output)
            command = [sys.executable, 'runtime.py', 'offline', '--manifest',
                       str(ROOT / 'execution-manifest.json'), '--case', case,
                       '--candidate', candidate, '--output', str(offline_output),
                       '--python', sys.executable]
            run(command, SCRATCH / f'offline-{suffix}-{key}-stdout.log')
            offline_log = folder / f'offline-{key}.log'
            offline_log.write_text((offline_output / 'offline.log').read_text().rstrip('\n') + '\n')
            target['offline'] = {'command': shlex.join(command), 'exit_code': 0,
                                 'construction_sha256': target['construction_sha256'],
                                 'log': str(offline_log.relative_to(ROOT)),
                                 'log_sha256': sha(offline_log)}
            save_manifest(manifest)
            print(suffix, candidate, 'offline passed', flush=True)
            if candidate == 'primary' and suffix == 'same_lane_pass':
                compatibility_output = SCRATCH / 'compat-same-lane-primary-v4'
            else:
                compatibility_output = SCRATCH / f'compat-{suffix}-{key}-proof'
                if compatibility_output.exists():
                    shutil.rmtree(compatibility_output)
                command = [sys.executable, 'runtime.py', 'compatibility',
                           '--manifest', str(ROOT / 'execution-manifest.json'),
                           '--case', case, '--candidate', candidate,
                           '--output', str(compatibility_output),
                           '--library', 'runtime/library',
                           '--validator', str(VALIDATOR)]
                run(command, SCRATCH / f'compat-{suffix}-{key}-stdout.log')
            proof = json.loads((compatibility_output / 'compatibility.json').read_text())
            if (proof['case_id'] != case or proof['candidate_id'] != candidate or
                    proof['construction_sha256'] != target['construction_sha256'] or
                    proof['passed'] is not True):
                raise ValueError('Compatibility receipt binds another construction')
            receipt = folder / f'compatibility-{key}.json'
            positive = folder / f'compatibility-{key}-analysis.log'
            negative = folder / f'compatibility-{key}-negative.log'
            for source, destination in (
                ('compatibility.json', receipt),
                ('compatibility-analysis.log', positive),
                ('negative-analysis.log', negative),
            ):
                shutil.copyfile(compatibility_output / source, destination)
            target['compatibility'] = {
                'receipt': str(receipt.relative_to(ROOT)), 'sha256': sha(receipt),
                'log': str(positive.relative_to(ROOT)),
                'negative_log': str(negative.relative_to(ROOT)),
            }
            if candidate == 'primary':
                entry['negative'] = {'log': str(negative.relative_to(ROOT))}
            save_manifest(manifest)
            print(suffix, candidate, 'compatibility passed', flush=True)


if __name__ == '__main__':
    main()
