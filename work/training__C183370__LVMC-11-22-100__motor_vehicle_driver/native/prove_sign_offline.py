"""Pinned offline CPU checks for the four sign cases and risk candidates."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
MANIFEST = PACKAGE / 'draft-sign-capture-manifest.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run():
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO / '.runtime-work/pipeline-output-c183370-update113')
    rows = []
    for entry in manifest['cases']:
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            case = entry['case_id']
            label = case.removeprefix(PACKAGE.name + '__') + '-' + candidate
            target = REPO / '.runtime-work' / ('c183370-update113-' + label + '-offline')
            if target.exists():
                target = target.with_name(target.name + '-fresh')
            log = PACKAGE / ('update113-' + label + '-offline.log')
            command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
                       'offline', '--manifest', str(MANIFEST), '--case', case,
                       '--candidate', candidate, '--output', str(target),
                       '--python', str(REPO / '.venv-cpu/bin/python')]
            with log.open('w') as stream:
                subprocess.run(command, cwd=REPO, env=env, stdout=stream,
                               stderr=subprocess.STDOUT, check=True)
            selected = entry if candidate == 'primary' else next(
                c for c in entry['candidates'] if c['id'] == candidate)
            rows.append({'case_id': case, 'candidate': candidate,
                         'construction_sha256': selected['construction_sha256'],
                         'offline_log_sha256': sha(log)})
            print(label, 'passed', flush=True)
    path = PACKAGE / 'update113-sign-offline-matrix.json'
    path.write_text(json.dumps({'format': 'c183370-sign-offline-matrix-v1',
                                'manifest_sha256': sha(MANIFEST), 'rows': rows},
                               indent=2, sort_keys=True) + '\n')
    return path


if __name__ == '__main__':
    print(run())
