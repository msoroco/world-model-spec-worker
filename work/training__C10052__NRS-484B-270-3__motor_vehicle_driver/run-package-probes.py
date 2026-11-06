"""Run all eight unselected exact v1 synthetic package positive/negative probes."""
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def run():
    env = dict(os.environ)
    env['PATH'] = str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+env.get('PATH', '')
    env['LD_LIBRARY_PATH'] = str(ROOT/'.runtime-work/geos-wheel/shapely.libs')+os.pathsep+env.get('LD_LIBRARY_PATH', '')
    rows = []
    for suffix in ('probe_a', 'probe_b'):
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            command = [str(ROOT/'.venv-cpu/bin/python'), str(HERE/'probe-package-compatibility.py'),
                       '--suffix', suffix, '--candidate', candidate]
            completed = subprocess.run(command, cwd=HERE, env=env, text=True,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       timeout=300)
            name = 'package-compatibility-'+suffix+('' if candidate == 'primary' else '-'+candidate)+'.log'
            (HERE/name).write_text(completed.stdout)
            rows.append({'suffix': suffix, 'candidate': candidate,
                         'exit_code': completed.returncode, 'log': name})
            print(suffix, candidate, 'exit', completed.returncode, flush=True)
    result = {'format': 'c10052-v1-package-probe-run-v1', 'rows': rows,
              'status': 'unselected_synthetic_diagnostic'}
    (HERE/'package-probe-run-summary.json').write_text(json.dumps(result, indent=2)+'\n')
    if any(row['exit_code'] for row in rows):
        raise SystemExit(1)
    return result


if __name__ == '__main__':
    run()
