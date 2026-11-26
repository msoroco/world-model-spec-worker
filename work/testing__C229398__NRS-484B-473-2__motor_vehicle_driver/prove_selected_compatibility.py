"""Exercise all selected bundles through pinned analysis, Native, Core and video."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from parked_lamps import CASES
from source_packet import ASSIGNMENT

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VALIDATOR = ROOT / '.runtime-work/c110969-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean_log(source, target):
    data = Path(source).read_text(errors='replace').rstrip() + '\n'
    Path(target).write_text(data)


def prove():
    if not VALIDATOR.is_file():
        raise ValueError('pinned Lean adapterCheck executable absent')
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if {entry['case_id'] for entry in manifest['cases']} != {
            ASSIGNMENT + '__' + case.name for case in CASES}:
        raise ValueError('selected parked-light case inventory changed')
    scratch = ROOT / '.runtime-work/c229398-selected-compat'
    scratch.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work/c229398-output')
    env['TMPDIR'] = str(ROOT / '.runtime-work/c229398-tmp')
    Path(env['SCENARIO_PIPELINE_OUTPUT_ROOT']).mkdir(parents=True, exist_ok=True)
    Path(env['TMPDIR']).mkdir(parents=True, exist_ok=True)
    for entry in manifest['cases']:
        name = entry['case_id'].removeprefix(ASSIGNMENT + '__')
        for candidate in ('primary', 'fallback1'):
            ref = entry if candidate == 'primary' else entry['candidates'][0]
            output = scratch / name / candidate
            output.parent.mkdir(parents=True, exist_ok=True)
            if output.exists():
                shutil.rmtree(output)
            command = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
                       'compatibility', '--manifest', str(manifest_path),
                       '--case', entry['case_id'], '--output', str(output),
                       '--library', str(ROOT / 'runtime/library'),
                       '--validator', str(VALIDATOR)]
            if candidate != 'primary':
                command.extend(['--candidate', candidate])
            run = subprocess.run(command, cwd=ROOT, env=env,
                                 capture_output=True, text=True)
            if run.returncode:
                raise ValueError(name + '/' + candidate + ' compatibility failed: ' +
                                 (run.stdout + run.stderr)[-2000:])
            receipt_source = output / 'compatibility.json'
            receipt = json.loads(receipt_source.read_text())
            if (receipt['case_id'] != entry['case_id'] or
                    receipt['construction_sha256'] != ref['construction_sha256'] or
                    not receipt['passed'] or
                    receipt['negative_removed'] != 'parking_lawfulness.txt'):
                raise ValueError('case-specific compatibility receipt differs')
            prefix = f'cpu-compat-{name}-{candidate}'
            receipt_file = HERE / (prefix + '-receipt.json')
            log = HERE / (prefix + '-analysis.log')
            negative = HERE / (prefix + '-negative.log')
            receipt_file.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
            clean_log(output / 'compatibility-analysis.log', log)
            clean_log(output / 'negative-analysis.log', negative)
            ref['compatibility'] = {'command': ' '.join(command),
                                    'receipt': receipt_file.name,
                                    'sha256': sha(receipt_file),
                                    'log': log.name,
                                    'negative_log': negative.name,
                                    'negative_log_sha256': sha(negative)}
            if candidate == 'primary':
                entry['negative'] = {'log': negative.name,
                                     'log_sha256': sha(negative)}
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return len(manifest['cases']) * 2


if __name__ == '__main__':
    print(prove())
