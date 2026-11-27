"""Prepare a fresh recorded-only CPU replay from exact compatibility sources."""

import argparse
import hashlib
import json
import subprocess
import shutil
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work'
SOURCES = ('capture', 'trace.jsonl', 'video_frames.jsonl',
           'interaction-rows.json', 'context-original.json',
           'diagnostic-source-note.json', 'acquisition-provenance.json',
           'road.xodr', 'overview.mkv', 'approach.mkv',
           'reference_corner.mkv', 'driver_reference.mkv')


def prepare(case_id, compat, output):
    output = Path(output).resolve()
    compat = Path(compat).resolve()
    if (SCRATCH.resolve() not in output.parents or output.exists() or
            SCRATCH.resolve() not in compat.parents):
        raise ValueError('fresh source and destination belong under .runtime-work')
    manifest = HERE / 'diagnostic-execution-manifest.json'
    entries = {case['case_id']: case for case in
               json.loads(manifest.read_text())['cases']}
    if case_id not in entries:
        raise ValueError('exact case required')
    receipt = json.loads((compat / 'compatibility.json').read_text())
    if (receipt.get('passed') is not True or
            receipt.get('case_id') != case_id or
            receipt.get('construction_sha256') !=
            entries[case_id]['construction_sha256']):
        raise ValueError('current exact compatibility donor required')
    subprocess.run([str(ROOT / '.venv-cpu/bin/python'),
                    str(ROOT / 'runtime.py'), 'materialize',
                    '--manifest', str(manifest), '--case', case_id,
                    '--output', str(output)], cwd=ROOT, check=True)
    (output / 'candidate-selection.json').unlink()
    for name in SOURCES:
        source = compat / name
        target = output / name
        if not source.exists() or target.exists():
            raise ValueError('missing or shadowed diagnostic source: ' + name)
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
    return {'case_id': case_id, 'source_compatibility_sha256':
            hashlib.sha256((compat / 'compatibility.json').read_bytes()).hexdigest(),
            'attempt': str(output), 'synthetic_only': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--compat', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.case, args.compat, args.output)))
