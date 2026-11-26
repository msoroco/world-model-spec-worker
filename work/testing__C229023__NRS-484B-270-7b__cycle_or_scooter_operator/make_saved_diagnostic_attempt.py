"""Prepare a fresh synthetic saved-only replay from a compatibility fixture."""

import argparse
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work'
SOURCES = ('capture', 'trace.jsonl', 'video_frames.jsonl',
           'pass-rows.json', 'diagnostic-source-note.json',
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
    donor = SCRATCH / 'c229023-owner' / ('compat-' + candidate + '-' + name + '-sweep2')
    if not (donor / 'compatibility.json').is_file():
        raise ValueError('tested exact compatibility donor missing')
    manifest = HERE / 'execution-manifest.json'
    command = ['.venv-cpu/bin/python', 'runtime.py', 'materialize',
               '--manifest', str(manifest), '--case', case_id,
               '--output', str(output)]
    if candidate != 'primary':
        command.extend(['--candidate', candidate])
    subprocess.run(command, cwd=ROOT, check=True)
    for name in SOURCES:
        source = donor / name
        target = output / name
        if not source.exists() or target.exists():
            raise ValueError('missing or shadowed diagnostic source: ' + name)
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
