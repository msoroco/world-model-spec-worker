"""Bind selected exact-case positive and missing-source compatibility proofs."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
SCRATCH = REPO / '.runtime-work/c227824-selected-compat'
VALIDATOR = REPO / '.runtime-work/c229439-validator/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove():
    if not VALIDATOR.is_file():
        raise ValueError('pinned Lean adapterCheck missing')
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ)
    env['TMPDIR'] = str(REPO / '.runtime-work/c227824-selected-tmp')
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO / '.runtime-work/c227824-selected-output')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    Path(env['TMPDIR']).mkdir(parents=True, exist_ok=True)
    Path(env['SCENARIO_PIPELINE_OUTPUT_ROOT']).mkdir(parents=True, exist_ok=True)
    for entry in manifest['cases']:
        cid = entry['case_id']
        suffix = cid.removeprefix(HERE.name + '__')
        for candidate in ('primary', 'fallback1'):
            ref = entry if candidate == 'primary' else entry['candidates'][0]
            output = SCRATCH / suffix / candidate
            if output.exists():
                shutil.rmtree(output)
            output.parent.mkdir(parents=True, exist_ok=True)
            command = [sys.executable, str(REPO / 'runtime.py'), 'compatibility',
                       '--manifest', str(MANIFEST), '--case', cid,
                       '--output', str(output), '--library', str(REPO / 'runtime/library'),
                       '--validator', str(VALIDATOR)]
            if candidate != 'primary':
                command.extend(['--candidate', candidate])
            done = subprocess.run(command, cwd=REPO, env=env, capture_output=True,
                                  text=True, timeout=600)
            if done.returncode:
                raise ValueError(cid + '/' + candidate + ' compatibility failed: ' +
                                 (done.stdout + done.stderr)[-1500:])
            receipt = json.loads((output / 'compatibility.json').read_text())
            if (receipt['case_id'] != cid or receipt['candidate_id'] != candidate or
                    receipt['construction_sha256'] != ref['construction_sha256'] or
                    receipt['negative_removed'] != 'device-history.jsonl'):
                raise ValueError('selected compatibility receipt differs')
            target = HERE / 'cases' / suffix
            prefix = 'selected-compat-' + candidate
            rec = target / (prefix + '-receipt.json')
            log = target / (prefix + '-analysis.log')
            negative = target / (prefix + '-negative.log')
            log.write_text((output / 'compatibility-analysis.log').read_text().rstrip() + '\n')
            negative.write_text((output / 'negative-analysis.log').read_text().rstrip() + '\n')
            receipt['log_sha256'] = sha(log)
            receipt['negative_log_sha256'] = sha(negative)
            rec.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
            ref['compatibility'] = {'command': ' '.join(command),
                                    'receipt': str(rec.relative_to(HERE)),
                                    'sha256': sha(rec),
                                    'log': str(log.relative_to(HERE)),
                                    'negative_log': str(negative.relative_to(HERE)),
                                    'negative_log_sha256': sha(negative)}
            if candidate == 'primary':
                entry['negative'] = {'log': str(negative.relative_to(HERE)),
                                     'log_sha256': sha(negative)}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    return len(manifest['cases']) * 2


if __name__ == '__main__':
    print(prove())
