"""Exercise selected source acceptance in diagnostic and removed-road modes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(condition):
    if condition not in ('probe_a', 'probe_b'):
        raise ValueError('Unknown exact condition')
    case = HERE.name + '__' + condition
    scratch = ROOT / '.runtime-work/c110919-8c-owner104'
    source = scratch / f'saved-{condition}-primary/attempt'
    processing = scratch / f'saved-{condition}-primary/processed/v0001/processing.json'
    if not source.is_dir() or not processing.is_file():
        raise ValueError('Recorded-only primary source proof missing')
    script = HERE / 'delivery_audit.py'
    positive = [sys.executable, str(script), '--case', case, '--candidate', 'primary',
                '--attempt', str(source), '--processing', str(processing),
                '--output', str(scratch / f'delivery-{condition}-positive.json'), '--diagnostic']
    result = subprocess.run(positive, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=60)
    positive_log = HERE / f'current-delivery-{condition}-positive.log'
    positive_log.write_text(result.stdout)
    if result.returncode or not json.loads((scratch / f'delivery-{condition}-positive.json').read_text()).get('diagnostic_only'):
        raise ValueError('Diagnostic delivery positive failed')
    negative_source = scratch / f'delivery-{condition}-negative-attempt'
    shutil.copytree(source, negative_source, copy_function=os.link)
    (negative_source / 'road_geometry.json').unlink()
    negative = [sys.executable, str(script), '--case', case, '--candidate', 'primary',
                '--attempt', str(negative_source), '--processing', str(processing),
                '--output', str(scratch / f'delivery-{condition}-negative.json'), '--diagnostic']
    result = subprocess.run(negative, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=60)
    negative_log = HERE / f'current-delivery-{condition}-negative.log'
    negative_log.write_text(result.stdout)
    if result.returncode == 0 or 'Missing original source: road_geometry.json' not in result.stdout:
        raise ValueError('Missing-road acceptance negative failed')
    print(json.dumps({'condition': condition, 'positive_sha256': sha(positive_log),
                      'negative_sha256': sha(negative_log)}))


if __name__ == '__main__':
    run(sys.argv[1])
