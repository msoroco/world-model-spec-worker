"""Fresh source-complete saved processing for the nine exact rider cases."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize
from worker_exchange.fixture_recipe import materialize as materialize_fixture

PY = str(REPO / '.venv-cpu/bin/python')
PREFIX = 'heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator__'
MANIFESTS = {
    'bicycle_signal_once': 'first-execution-manifest.json',
    'bicycle_no_signal': 'no-signal-manifest.json',
    'bicycle_signal_continuous': 'continuous-manifest.json',
    'electric_bicycle_signal_once': 'electric-bicycle-manifest.json',
    'electric_scooter_signal_once': 'electric-scooter-manifest.json',
    'turn_lane_no_signal': 'turn-lane-manifest.json',
    'both_hands_no_signal': 'both-hands-manifest.json',
    'safety_wide': 'safety-wide-manifest.json',
    'safety_narrow': 'safety-narrow-manifest.json',
}

for slug, filename in MANIFESTS.items():
    manifest = ROOT / filename
    case = PREFIX + slug
    folder = ROOT / 'cases' / slug
    attempt = REPO / '.runtime-work' / f'c111588-common-{slug}-saved-attempt-k'
    output = REPO / '.runtime-work' / f'c111588-common-{slug}-saved-proof-j'
    if not attempt.exists():
        materialize(manifest, case, attempt)
        with tempfile.TemporaryDirectory(prefix='rider-common-sources-', dir=REPO / '.runtime-work') as temporary:
            source = Path(temporary) / 'fixture'
            recipe = ROOT / 'diagnostic-recipe.json' if slug == 'bicycle_signal_once' else folder / 'diagnostic-recipe.json'
            materialize_fixture(REPO, recipe, source)
            for path in source.iterdir():
                target = attempt / path.name
                if target.exists():
                    raise ValueError(f'Diagnostic source shadows construction: {path.name}')
                if path.is_dir():
                    shutil.copytree(path, target)
                else:
                    shutil.copy2(path, target)
    command = [PY, 'runtime.py', 'process-saved', '--manifest', str(manifest.relative_to(REPO)),
               '--case', case, '--attempt', str(attempt.relative_to(REPO)),
               '--output', str(output.relative_to(REPO)), '--library', 'runtime/library',
               '--validator', '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
    log = folder / 'saved-processing-j.log'
    if not (output / 'v0001/processing.json').exists():
        with log.open('w') as stream:
            result = subprocess.run(command, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(f'{slug}: {log.read_text()[-2000:]}')
    saved = output / 'v0001'
    shutil.copy2(saved / 'processing.json', folder / 'saved-receipt-j.json')
    shutil.copy2(saved / 'analysis.log', folder / 'saved-analysis-j.log')
    print(slug, 'source-complete saved processing passed', flush=True)
