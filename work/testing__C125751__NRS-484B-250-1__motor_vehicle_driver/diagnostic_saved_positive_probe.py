"""Push synthetic saved processing through analysis and media to expose gaps."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from case_protocol import ASSIGNMENT

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from test_analysis import write_attempt


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    scratch = REPO / '.runtime-work' / 'c125751-diagnostic-runtime-3'
    (scratch / 'proposals').mkdir(exist_ok=True)
    shutil.copy2(ROOT / 'proposals' / 'cases.json', scratch / 'proposals' / 'cases.json')
    attempt = scratch / 'saved-attempt-source-shaped-3'
    if attempt.exists():
        raise ValueError('Retain prior synthetic source-shaped attempt')
    shutil.copytree(scratch / 'offline' / 'precedence', attempt)
    for name in ('candidate-selection.json', 'offline.log'):
        (attempt / name).unlink()
    original_config = (attempt / 'config.json').read_bytes()
    original_construction = (attempt / 'construction.json').read_bytes()
    write_attempt(attempt)
    (attempt / 'config.json').write_bytes(original_config)
    (attempt / 'construction.json').write_bytes(original_construction)
    history_path = attempt / 'signal-history.json'
    history = json.loads(history_path.read_text())
    for row in history['frames']:
        row['ego_next_tick_request'] = 'proceed'
    history_path.write_text(json.dumps(history) + '\n')
    signal_packet_path = attempt / 'signal-packet.json'
    signal_packet = json.loads(signal_packet_path.read_text())
    signal_packet['case_id'] = ASSIGNMENT + '__precedence'
    signal_packet['payload_sha256'] = sha(history_path)
    signal_packet_path.write_text(json.dumps(signal_packet) + '\n')
    inventory_path = attempt / 'acquisition.json'
    inventory = json.loads(inventory_path.read_text())
    for name in ('signal-history.json', 'signal-packet.json'):
        inventory[name]['sha256'] = sha(attempt / name)
    inventory_path.write_text(json.dumps(inventory) + '\n')
    dimensions = {'overview': (1920, 1080), 'approach': (1280, 720),
                  'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}
    for name, (width, height) in dimensions.items():
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                        '-n', '-f', 'lavfi', '-i', f'color=c=black:s={width}x{height}:r=20',
                        '-frames:v', '6', '-an', '-c:v', 'ffv1', '-threads', '1',
                        str(attempt / (name + '.mkv'))], check=True, timeout=120)
    before = {p.name: sha(p) for p in attempt.iterdir() if p.is_file()}
    output = scratch / 'saved-source-shaped-output-3'
    command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
               'process-saved', '--manifest', str(scratch / 'saved-manifest.json'),
               '--case', ASSIGNMENT + '__precedence', '--attempt', str(attempt),
               '--output', str(output), '--library', str(REPO / 'runtime/library'),
               '--validator', str(REPO / 'runtime/library/Main.lean')]
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO / '.runtime-work' / 'c125751-proof')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    completed = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
    log = scratch / 'saved-source-shaped-3.log'
    log.write_text(completed.stdout + completed.stderr)
    after = {p.name: sha(p) for p in attempt.iterdir() if p.is_file()}
    feedback_path = output / 'v0001' / 'feedback.json'
    receipt = {'diagnostic_fixture': True, 'case_id': ASSIGNMENT + '__precedence',
               'exit_code': completed.returncode, 'originals_preserved': before == after,
               'analysis_log_sha256': sha(output / 'v0001/analysis.log')
               if (output / 'v0001/analysis.log').is_file() else None,
               'feedback': json.loads(feedback_path.read_text())
               if feedback_path.is_file() else None,
               'production_acceptance_claimed': False}
    (scratch / 'diagnostic-saved-positive-probe-3.json').write_text(
        json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))
    if not receipt['originals_preserved']:
        raise ValueError('Saved processing mutated synthetic acquisition')


if __name__ == '__main__':
    main()
