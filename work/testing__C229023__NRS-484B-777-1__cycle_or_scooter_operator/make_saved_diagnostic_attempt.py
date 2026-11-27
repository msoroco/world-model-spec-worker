"""Prepare a fresh synthetic saved-only replay from an exact compatibility fixture."""

import argparse
import shutil
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work' / 'c229023-7771-owner-nov26'
SOURCES = ('capture', 'trace.jsonl', 'video_frames.jsonl',
           'rightside-rows.json', 'diagnostic-source-note.json',
           'acquisition-provenance.json', 'road.xodr',
           'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
           'driver_reference.mkv')


def prepare(case_id, candidate, output):
    output = Path(output).resolve()
    if SCRATCH.resolve() not in output.parents or output.exists():
        raise ValueError('fresh diagnostic attempt belongs under .runtime-work')
    name = case_id.removeprefix(HERE.name + '__')
    if name == case_id:
        raise ValueError('exact assignment case required')
    donor = SCRATCH / ('compat-v5-' + name +
                       ('' if candidate == 'primary' else '-fallback1'))
    if not (donor / 'compatibility.json').is_file():
        raise ValueError('tested exact compatibility donor missing')
    manifest = HERE / 'execution-manifest.draft.json'
    command = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
               'materialize', '--manifest', str(manifest), '--case', case_id,
               '--output', str(output)]
    if candidate != 'primary':
        command.extend(['--candidate', candidate])
    subprocess.run(command, cwd=ROOT, check=True)
    for item in SOURCES:
        source = donor / item
        target = output / item
        if not source.exists() or target.exists():
            raise ValueError('missing or shadowed diagnostic source: ' + item)
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
    if candidate == 'primary':
        (output / 'candidate-selection.json').unlink()
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', default='primary')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(prepare(args.case, args.candidate, args.output))
