"""Run pinned saved processing from fresh selected acquisition sources."""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest-draft.json'
CASE = ROOT.name + '__reference'
PREFIX = REPO / '.runtime-work/c146314-210-2-reference-primary-fresh-update056d'
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


run('fixture', '--recipe', ROOT / 'selected-diagnostics/reference/primary-recipe.json',
    '--output', FIXTURE)
run('materialize', '--manifest', MANIFEST, '--case', CASE,
    '--output', ATTEMPT)
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
