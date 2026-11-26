"""Run independent saved-source comparison positives and mutation negatives."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPT = HERE / 'audit_comparison.py'
NAMES = ('route-trace.jsonl', 'route-context.json', 'road.xodr', 'video_frames.jsonl')
PAIRS = (
    ('witness', 'route_choice', 'c230259_627_witness1_primary_compat_v4',
     'c230259_627_witness_2_primary_compat_v1'),
    ('exception_1', 'route_availability', 'c230259_627_exception_1_1_primary_compat_v1',
     'c230259_627_exception_1_2_primary_compat_v1'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    target = HERE / 'comparison-proof'
    target.mkdir(exist_ok=True)
    receipts = []
    for name, mode, left_name, right_name in PAIRS:
        left = ROOT / '.runtime-work' / left_name
        right = ROOT / '.runtime-work' / right_name
        command = [sys.executable, '-B', str(SCRIPT), '--left', str(left),
                   '--right', str(right), '--mode', mode]
        positive = subprocess.run(command, cwd=ROOT, env=os.environ.copy(),
                                  text=True, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT)
        if positive.returncode:
            raise ValueError('Comparison positive failed: ' + positive.stdout[-1000:])
        positive_path = target / (name + '-positive.log')
        positive_path.write_text(positive.stdout.rstrip() + '\n')
        payload = json.loads(positive.stdout)
        mutated = ROOT / '.runtime-work' / ('c230259_627_' + name + '_comparison_negative_v1')
        mutated.mkdir(parents=True, exist_ok=False)
        for item in NAMES:
            shutil.copyfile(right / item, mutated / item)
        rows = [json.loads(line) for line in (mutated / 'route-trace.jsonl').read_text().splitlines()]
        rows[100]['time_s'] += .25
        (mutated / 'route-trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
        negative_command = command.copy()
        negative_command[negative_command.index(str(right))] = str(mutated)
        negative = subprocess.run(negative_command, cwd=ROOT, env=os.environ.copy(),
                                  text=True, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT)
        if negative.returncode == 0 or 'original route/camera time join differs' not in negative.stdout:
            raise ValueError('Comparison did not reject timestamp mutation: ' + negative.stdout[-1000:])
        negative_path = target / (name + '-negative.log')
        negative_path.write_text(negative.stdout.rstrip() + '\n')
        receipts.append({'comparison': name, 'mode': mode,
                         'positive_command': ' '.join(command),
                         'positive_log': str(positive_path.relative_to(HERE)),
                         'positive_log_sha256': sha(positive_path), 'positive_exit_code': 0,
                         'negative_command': ' '.join(negative_command),
                         'negative_log': str(negative_path.relative_to(HERE)),
                         'negative_log_sha256': sha(negative_path),
                         'negative_exit_code': negative.returncode,
                         'left_source_hashes': payload['left_source_sha256'],
                         'right_source_hashes': payload['right_source_sha256'],
                         'source_kind': 'synthetic_fixture',
                         'original_native_capture_attested': False})
        print(json.dumps({'comparison': name, 'positive': 0,
                          'negative': negative.returncode}), flush=True)
    index = target / 'index.json'
    index.write_text(json.dumps({'format': 'c230259-route-comparison-proof-v1',
                                 'audit_script_sha256': sha(SCRIPT),
                                 'comparisons': receipts}, indent=2) + '\n')


if __name__ == '__main__':
    main()
