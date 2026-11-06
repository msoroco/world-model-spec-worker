"""Refresh all eight exact unselected v1 CPU package diagnostics."""
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    env = dict(os.environ)
    env['PATH'] = str(ROOT / '.runtime-work/linux_arm64') + os.pathsep + env.get('PATH', '')
    env['LD_LIBRARY_PATH'] = str(ROOT / '.runtime-work/geos-wheel/shapely.libs')
    results = []
    for suffix in ('reference', 'contrast'):
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            command = [str(ROOT / '.venv-cpu/bin/python'), str(HERE / 'probe-package-crosswalk.py'),
                       '--suffix', suffix, '--candidate', candidate]
            run = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
            log = HERE / f'package-{suffix}-{candidate}.log'
            log.write_text(run.stdout)
            if run.returncode:
                raise ValueError(f'{suffix}/{candidate} pinned package failed: {run.stdout[-1800:]}')
            receipt = json.loads(run.stdout.splitlines()[-1])
            assert receipt['positive']['passed'] and receipt['negative']['exit_code'] != 0
            results.append({'suffix': suffix, 'candidate': candidate,
                            'construction_sha256': receipt['positive']['construction_sha256'],
                            'log': log.name})
            print(json.dumps({'suffix': suffix, 'candidate': candidate,
                              'passed': True}), flush=True)
    print(json.dumps({'exact_v1_positives': len(results),
                      'removed_source_negatives': len(results), 'selected': False}))


if __name__ == '__main__':
    main()
