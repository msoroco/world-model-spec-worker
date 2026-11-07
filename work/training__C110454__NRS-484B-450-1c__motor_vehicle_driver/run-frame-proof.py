"""Refresh pinned offline and exact synthetic portable proofs for eight drafts."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PYTHON = ROOT / '.venv-cpu/bin/python'
MANIFEST = HERE / 'draft-execution-manifest.json'


def command(argv, env, timeout=600):
    result = subprocess.run(argv, cwd=ROOT, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    if result.returncode:
        raise RuntimeError('Command failed: ' + ' '.join(argv) + '\n' + result.stdout)
    return result.stdout


def run():
    manifest = json.loads(MANIFEST.read_text())
    if manifest['status'] != 'draft_not_selected' or len(manifest['cases']) != 2:
        raise ValueError('Expected two unselected controlled cases')
    env = dict(os.environ)
    env['LD_LIBRARY_PATH'] = str(ROOT / '.runtime-work/geos-wheel/shapely.libs') + os.pathsep + env.get('LD_LIBRARY_PATH', '')
    env['PATH'] = str(ROOT / '.runtime-work/linux_arm64') + os.pathsep + env.get('PATH', '')
    scratch = Path(tempfile.mkdtemp(prefix='c110454-450-frame-', dir=ROOT / '.runtime-work'))
    receipts = []
    for suffix in ('probe_a', 'probe_b'):
        fixture_result = command([str(PYTHON), str(HERE / 'probe-portable.py'),
                                  '--suffix', suffix, '--fixture-only'], env)
        fixture = Path(json.loads(fixture_result)['fixture'])
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            case = HERE.name + '__' + suffix
            destination = scratch / (suffix + '-' + candidate)
            offline_result = command([str(PYTHON), str(ROOT / 'runtime.py'), 'offline',
                                      '--manifest', str(MANIFEST), '--case', case,
                                      '--candidate', candidate, '--output', str(destination),
                                      '--python', str(PYTHON)], env, timeout=300)
            receipt = json.loads(offline_result)
            log = destination / 'offline.log'
            if 'Ran 5 tests' not in log.read_text():
                raise ValueError('Exact bundle did not run the new Native speed test')
            receipts.append({'case': suffix, 'candidate': candidate,
                             'offline_passed': receipt['offline_passed'],
                             'log': str(log.relative_to(ROOT)),
                             'construction_sha256': next(
                                 c['construction_sha256'] for e in manifest['cases']
                                 if e['case_id'] == case for c in
                                 ([e] if candidate == 'primary' else e['candidates'])
                                 if c['id'] == candidate)})
            command([str(PYTHON), str(HERE / 'probe-portable.py'), '--suffix', suffix,
                     '--candidate', candidate, '--reuse-fixture', str(fixture)], env)
            print(suffix, candidate, 'offline and portable passed', flush=True)
    (HERE / 'pinned-offline-proof.log').write_text(json.dumps({
        'passed': True, 'scope': 'pinned runtime.py offline exact materialized bundles; no CARLA',
        'results': receipts}, indent=2) + '\n')


if __name__ == '__main__':
    run()
