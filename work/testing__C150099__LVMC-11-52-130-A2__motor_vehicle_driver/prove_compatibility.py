"""Run and bind exact synthetic compatibility proofs without physical claims."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(REPO / '.runtime-work'))
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(ROOT.name + '__')
        output = REPO / '.runtime-work' / ('c150099-compat-' + suffix + '-v10')
        if not output.exists():
            command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
                       'compatibility', '--manifest', str(MANIFEST), '--case',
                       entry['case_id'], '--output', str(output), '--library',
                       str(REPO / 'runtime/library'), '--validator',
                       str(REPO / '.runtime-work/c150099-decoder-v2/.lake/build/bin/adapterCheck')]
            run = subprocess.run(command, cwd=REPO, env=env, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if run.returncode:
                raise ValueError('compatibility failed for ' + suffix + ': ' + run.stdout[-1200:])
        if not (output / 'compatibility.json').is_file():
            raise ValueError('compatibility receipt absent for ' + suffix)
        targets = {'compatibility.json': 'cpu-compat-' + suffix + '.json',
                   'compatibility-analysis.log': 'cpu-compat-analysis-' + suffix + '.log',
                   'negative-analysis.log': 'cpu-compat-negative-' + suffix + '.log'}
        for source, target in targets.items():
            shutil.copyfile(output / source, ROOT / target)
        proof = json.loads((ROOT / targets['compatibility.json']).read_text())
        if not proof['passed'] or proof['case_id'] != entry['case_id']:
            raise ValueError('compatibility identity failed for ' + suffix)
        entry['compatibility'] = {'receipt': targets['compatibility.json'],
                                  'sha256': sha(ROOT / targets['compatibility.json']),
                                  'log': targets['compatibility-analysis.log']}
        entry['negative'] = {'log': targets['negative-analysis.log']}
        entry['acquisition'] = {channel['name']: {
            'entrypoint': 'analysis.py', 'method': 'saved_original_channel',
            'evidence': 'channels/' + channel['name'] + '.jsonl'}
            for channel in json.loads((ROOT / entry['construction']).read_text())
            ['recording_description']['channels']}
        entry['acquisition']['reviewed_fire_lane_packet'] = {
            'entrypoint': 'analysis.py', 'method': 'saved_original_context',
            'evidence': 'channels/context.json'}
        fallback = entry['candidates'][0]
        alternate = REPO / '.runtime-work' / ('c150099-compat-' + suffix + '-fallback1-v10')
        fallback_command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
                            'compatibility', '--manifest', str(MANIFEST), '--case',
                            entry['case_id'], '--candidate', 'fallback1', '--output',
                            str(alternate), '--library', str(REPO / 'runtime/library'),
                            '--validator',
                            str(REPO / '.runtime-work/c150099-decoder-v2/.lake/build/bin/adapterCheck')]
        attempt = subprocess.run(fallback_command, cwd=REPO, env=env, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if attempt.returncode:
            raise ValueError('fallback compatibility failed for ' + suffix + ': ' + attempt.stdout[-1200:])
        fallback_targets = {'compatibility.json': 'cpu-compat-fallback-' + suffix + '.json',
                            'compatibility-analysis.log': 'cpu-compat-analysis-fallback-' + suffix + '.log',
                            'negative-analysis.log': 'cpu-compat-negative-fallback-' + suffix + '.log'}
        for source, target in fallback_targets.items():
            shutil.copyfile(alternate / source, ROOT / target)
        fallback['compatibility'] = {
            'receipt': fallback_targets['compatibility.json'],
            'sha256': sha(ROOT / fallback_targets['compatibility.json']),
            'log': fallback_targets['compatibility-analysis.log'],
            'negative_log': fallback_targets['negative-analysis.log']}
        MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
        print('compatibility passed:', suffix, flush=True)


if __name__ == '__main__':
    main()
