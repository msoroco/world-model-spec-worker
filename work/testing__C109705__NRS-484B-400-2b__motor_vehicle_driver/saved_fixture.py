"""Stage a diagnostic source set and run the recorded-only processing command."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def run(*, case, kind, scratch):
    if not case.startswith(HERE.name + '__') or kind not in ('positive', 'missing_map'):
        raise ValueError('Exact saved fixture case or kind differs')
    name = case.removeprefix(HERE.name + '__')
    folder = Path(scratch).resolve()
    if REPO / '.runtime-work' not in folder.parents or folder.exists():
        raise ValueError('Use fresh saved fixture scratch under .runtime-work')
    folder.mkdir(parents=True)
    fixture, attempt, versions = (folder / part for part in ('fixture', 'attempt', 'versions'))
    python = REPO / '.venv-cpu/bin/python'
    runtime = REPO / 'runtime.py'
    manifest = HERE / 'execution-manifest.json'
    recipe = HERE / 'cases' / name / 'fixture-recipe.json'
    validator = REPO / '.runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck'
    env = dict(os.environ, TMPDIR=str(REPO / '.runtime-work/c109705-2b-nov24'),
               PYTHONDONTWRITEBYTECODE='1',
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / '.runtime-work/c109705-2b-nov24/pipeline'))
    def command(*args):
        return subprocess.run([str(python), str(runtime), *map(str, args)],
                              cwd=REPO, env=env, capture_output=True, text=True,
                              check=True).stdout
    command('fixture', '--recipe', recipe, '--output', fixture)
    command('materialize', '--manifest', manifest, '--case', case, '--output', attempt)
    for source in fixture.iterdir():
        destination = attempt / source.name
        if destination.exists():
            raise ValueError('Diagnostic fixture shadows selected package')
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
    if kind == 'missing_map':
        (attempt / 'original-map-packet.json').unlink()
    output = command('process-saved', '--manifest', manifest, '--case', case,
                     '--attempt', attempt, '--output', versions,
                     '--library', REPO / 'runtime/library', '--validator', validator)
    receipt = json.loads((versions / 'v0001/processing.json').read_text())
    if receipt.get('missing_evidence') != (kind == 'missing_map'):
        raise ValueError('Saved analysis completeness differs from fixture kind')
    print(json.dumps({'case_id': case, 'kind': kind, 'recorded_only': receipt['recorded_only'],
                      'analysis_complete': not receipt['missing_evidence'],
                      'originals_preserved': receipt['originals_preserved'],
                      'feedback': str(versions / 'v0001/feedback.json')
                      if (versions / 'v0001/feedback.json').is_file() else None}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', choices=('positive', 'missing_map'), required=True)
    parser.add_argument('--scratch', required=True)
    args = parser.parse_args()
    run(case=args.case, kind=args.kind, scratch=args.scratch)


if __name__ == '__main__':
    main()
