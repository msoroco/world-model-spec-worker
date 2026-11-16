"""Run one reference fallback through fresh pinned saved processing."""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
candidate = sys.argv[1]
witness = sys.argv[2] if len(sys.argv)>2 else 'reference'
if candidate not in ('primary', 'fallback1', 'fallback2', 'fallback3') or witness not in ('reference','contrast'):
    raise ValueError('Select one exact candidate and witness')
MANIFEST = ROOT / (
    'execution-manifest-contrast-draft.json' if candidate=='primary' and witness=='contrast'
    else 'execution-manifest-draft.json' if candidate=='primary'
    else 'execution-manifest-diagnostic-' + witness + '-' + candidate + '.json' if witness=='contrast'
    else 'execution-manifest-diagnostic-reference-' + candidate + '.json')
CASE = ROOT.name + '__' + witness
PREFIX = REPO / ('.runtime-work/c146314-210-2-' + witness + '-' + candidate + '-fresh-update063')
FIXTURE = Path(str(PREFIX) + '-fixture')
ATTEMPT = Path(str(PREFIX) + '-attempt')
SAVED = Path(str(PREFIX) + '-saved')
PYTHON = REPO / '.venv-cpu/bin/python'
RUNTIME = REPO / 'runtime.py'
LIBRARY = REPO / 'runtime/pipeline/library'
VALIDATOR = REPO / '.runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck'


def run(*args):
    subprocess.run([str(PYTHON), str(RUNTIME), *map(str, args)],
                   cwd=REPO, check=True)


run('fixture', '--recipe', ROOT / 'selected-diagnostics' / witness /
    (candidate + '-recipe.json'), '--output', FIXTURE)
run('materialize', '--manifest', MANIFEST, '--case', CASE,
    '--candidate', candidate, '--output', ATTEMPT)
for source in FIXTURE.iterdir():
    destination = ATTEMPT / source.name
    if destination.exists():
        raise ValueError('Fixture shadows selected package: ' + source.name)
    if source.is_dir():
        shutil.copytree(source, destination)
    else:
        shutil.copy2(source, destination)
run('process-saved', '--manifest', MANIFEST, '--case', CASE,
    '--attempt', ATTEMPT, '--output', SAVED,
    '--library', LIBRARY, '--validator', VALIDATOR)
