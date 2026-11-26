"""Run selected red-left positive and missing-source CPU compatibility proofs."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
DECODER = REPO / '.runtime-work/c150099-decoder-v2/.lake/build/bin/adapterCheck'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(entry: dict, candidate: str, suffix: str, env: dict) -> dict:
    output = REPO / '.runtime-work/c153046-nov25d' / ('compat-' + suffix + '-' + candidate + '-v7')
    if suffix == 'stopped_leftmost_clear' and candidate == 'primary':
        output = REPO / '.runtime-work/c153046-nov25d/compat-first-v9'
    command = [sys.executable, str(REPO / 'runtime.py'), 'compatibility', '--manifest',
               str(MANIFEST), '--case', entry['case_id'], '--candidate', candidate,
               '--output', str(output), '--library', str(REPO / 'runtime/library'),
               '--validator', str(DECODER)]
    if not (output / 'compatibility.json').is_file():
        process = subprocess.run(command, cwd=REPO, env=env, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if process.returncode:
            raise ValueError('compatibility failed: ' + suffix + '/' + candidate + '\n' +
                             process.stdout[-1800:])
    tag = suffix if candidate == 'primary' else 'fallback-' + suffix
    names = {'compatibility.json': 'cpu-compat-' + tag + '.json',
             'compatibility-analysis.log': 'cpu-compat-analysis-' + tag + '.log',
             'negative-analysis.log': 'cpu-compat-negative-' + tag + '.log'}
    for source, target in names.items():
        shutil.copyfile(output / source, ROOT / target)
    proof = json.loads((ROOT / names['compatibility.json']).read_text())
    if proof.get('passed') is not True or proof['case_id'] != entry['case_id'] or \
            proof['candidate_id'] != candidate:
        raise ValueError('compatibility identity differs: ' + suffix + '/' + candidate)
    return {'receipt': names['compatibility.json'],
            'sha256': sha(ROOT / names['compatibility.json']),
            'log': names['compatibility-analysis.log'],
            'negative_log': names['negative-analysis.log']}


def main() -> None:
    if not DECODER.is_file():
        raise ValueError('pinned Lean decoder executable unavailable')
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               TMPDIR=str(REPO / '.runtime-work/c153046-nov25d/tmp'),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / '.runtime-work/c153046-nov25d/output'))
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(ROOT.name + '__')
        entry['compatibility'] = run(entry, 'primary', suffix, env)
        entry['negative'] = {'log': entry['compatibility']['negative_log']}
        construction = json.loads((ROOT / entry['construction']).read_text())
        entry['acquisition'] = {channel['name']: {
            'entrypoint': 'analysis.py', 'method': 'saved_original_channel',
            'evidence': 'channels/' + channel['name'] + '.jsonl'}
            for channel in construction['recording_description']['channels']}
        entry['acquisition']['reviewed_red_left_site_packet'] = {
            'entrypoint': 'analysis.py', 'method': 'source-sealed original site packet',
            'evidence': 'channels/context.json'}
        entry['candidates'][0]['compatibility'] = run(entry, 'fallback1', suffix, env)
        MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
        print('compatibility passed:', suffix, 'primary + fallback', flush=True)


if __name__ == '__main__':
    main()
