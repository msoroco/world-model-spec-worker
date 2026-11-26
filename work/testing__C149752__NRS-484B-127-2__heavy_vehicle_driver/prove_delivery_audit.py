"""Exercise independent delivery protocol on explicitly synthetic fixtures."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from truck_following import CASES
from native_packet import AID, VIEWS

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c149752/delivery-protocol'
SCRIPT = HERE / 'delivery_audit.py'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean_log(path, result):
    content = (result.stdout + result.stderr).rstrip()
    path.write_text((content or ('exit_code=' + str(result.returncode))) + '\n',
                    encoding='utf-8')


def run():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    for case in CASES:
        name, case_id = case.suffix, AID + '__' + case.suffix
        attempt = ROOT / '.runtime-work/c149752' / ('compat-' + name + '-v5')
        if not (attempt / 'compatibility.json').is_file():
            raise ValueError('current exact diagnostic compatibility missing: ' + name)
        negative = SCRATCH / (name + '-missing-view')
        negative.mkdir(exist_ok=True)
        for filename in ('diagnostic-source-note.json', 'original-truck-history.jsonl',
                         'camera-frame-map.jsonl', 'video_frames.jsonl', 'compatibility.json'):
            source = attempt / filename
            target = negative / filename
            if not target.exists():
                os.link(source, target)
        for view in VIEWS:
            if view == 'approach':
                continue
            source = attempt / (view + '.mkv')
            target = negative / (view + '.mkv')
            if not target.exists():
                os.link(source, target)
        base = [sys.executable, str(SCRIPT), '--case', case_id,
                '--processed', str(SCRATCH / 'unused-synthetic-processed.json'),
                '--diagnostic-fixture', '--output']
        positive_command = base + [str(SCRATCH / (name + '-positive.json')),
                                   '--attempt', str(attempt)]
        negative_command = base + [str(SCRATCH / (name + '-negative.json')),
                                   '--attempt', str(negative)]
        env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),
                   TMPDIR=str(SCRATCH), PYTHONDONTWRITEBYTECODE='1')
        positive = subprocess.run(positive_command, cwd=ROOT, env=env,
                                  text=True, capture_output=True)
        failure = subprocess.run(negative_command, cwd=ROOT, env=env,
                                 text=True, capture_output=True)
        positive_log = HERE / ('delivery-positive-' + name + '.log')
        negative_log = HERE / ('delivery-negative-' + name + '.log')
        clean_log(positive_log, positive)
        clean_log(negative_log, failure)
        expected = 'Missing required source: approach.mkv'
        if positive.returncode or failure.returncode == 0 or expected not in negative_log.read_text():
            raise ValueError('diagnostic delivery protocol proof failed: ' + name)
        receipt = {'case_id': case_id, 'sets': ['demo-test', 'full-test'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': SCRIPT.name, 'script_sha256': sha(SCRIPT),
            'command': ' '.join(positive_command), 'test_exit_code': 0,
            'test_log': positive_log.name, 'test_log_sha256': sha(positive_log),
            'negative_command': ' '.join(negative_command),
            'negative_exit_code': failure.returncode,
            'negative_expected_error': expected,
            'negative_log': negative_log.name, 'negative_log_sha256': sha(negative_log),
            'diagnostic_scope': 'Synthetic protocol only; no physical or pixel acceptance claimed'}
        path = HERE / ('delivery-acceptance-' + name + '.json')
        path.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
        print(name + ': diagnostic delivery protocol positive and negative passed', flush=True)


if __name__ == '__main__':
    run()
