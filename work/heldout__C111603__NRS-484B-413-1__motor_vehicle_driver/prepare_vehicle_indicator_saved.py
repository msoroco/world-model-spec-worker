"""Materialize a fresh source-complete indicator diagnostic for saved processing."""
import argparse
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize
from worker_exchange.fixture_recipe import materialize as materialize_fixture

CASE = ROOT.name + '__vehicle_left_indicator'
parser = argparse.ArgumentParser()
parser.add_argument('--output', required=True)
args = parser.parse_args()
output = Path(args.output).resolve()
materialize(ROOT / 'vehicle-indicator-manifest.json', CASE, output)
with tempfile.TemporaryDirectory(prefix='c111603-indicator-source-', dir=REPO / '.runtime-work') as temporary:
    source = Path(temporary) / 'fixture'
    materialize_fixture(REPO, ROOT / 'vehicle-indicator-recipe.json', source)
    for path in source.iterdir():
        destination = output / path.name
        if destination.exists():
            raise ValueError('Diagnostic source shadows construction: ' + path.name)
        if path.is_dir():
            shutil.copytree(path, destination)
        else:
            shutil.copy2(path, destination)
print(CASE, 'fresh source-complete diagnostic materialized')
