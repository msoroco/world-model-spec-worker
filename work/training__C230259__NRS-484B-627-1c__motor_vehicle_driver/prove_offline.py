"""Run exact primary and fallback offline checks for each route case."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'draft-route-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    logs = HERE / 'offline'
    logs.mkdir(exist_ok=True)
    env = os.environ.copy()
    env['TMPDIR'] = str(ROOT / '.runtime-work')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work' / 'c230259_627_runtime')
    outcomes = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in ('primary', 'fallback1'):
            output = ROOT / '.runtime-work' / ('c230259_627_' + suffix + '_' + candidate + '_offline_v7')
            if output.exists():
                raise ValueError('Retain prior offline bundle; choose a fresh suffix: ' + str(output))
            command = ['.venv-cpu/bin/python', '-B', 'runtime.py', 'offline',
                '--manifest', str(MANIFEST.relative_to(ROOT)),
                '--case', entry['case_id'], '--candidate', candidate,
                '--output', str(output.relative_to(ROOT))]
            completed = subprocess.run(command, cwd=ROOT, env=env,
                                       capture_output=True, text=True, timeout=300)
            log = logs / (suffix + '-' + candidate + '.log')
            content = (completed.stdout + completed.stderr).rstrip() + '\n'
            content += (output / 'offline.log').read_text().rstrip() + '\n' if (output / 'offline.log').is_file() else ''
            log.write_text(content.rstrip() + '\n')
            if completed.returncode:
                raise RuntimeError('offline failed: ' + entry['case_id'] + '/' + candidate + ': ' + str(log))
            source = entry if candidate == 'primary' else entry['candidates'][0]
            source['offline'] = {'case_id': entry['case_id'], 'candidate_id': candidate,
                'construction_sha256': source['construction_sha256'],
                'command': ' '.join(command), 'exit_code': 0,
                'log': str(log.relative_to(HERE)), 'log_sha256': sha(log)}
            outcomes.append({'case_id': entry['case_id'], 'candidate': candidate,
                             'log_sha256': sha(log)})
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(outcomes))


if __name__ == '__main__':
    main()
