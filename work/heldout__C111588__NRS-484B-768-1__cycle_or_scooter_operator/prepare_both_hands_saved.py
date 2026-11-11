"""Materialize a fresh exact both-hands diagnostic with retained originals."""
import argparse
from pathlib import Path
import shutil
import tempfile

from worker_exchange.runtime_cli import materialize
from worker_exchange.fixture_recipe import materialize as materialize_fixture

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = 'heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator__both_hands_no_signal'
parser = argparse.ArgumentParser()
parser.add_argument('--output', required=True)
args = parser.parse_args()
output = Path(args.output).resolve()
materialize(ROOT / 'both-hands-manifest.json', CASE, output)
with tempfile.TemporaryDirectory(prefix='rider-hand-sources-', dir=REPO / '.runtime-work') as temporary:
    source = Path(temporary) / 'fixture'
    materialize_fixture(REPO, ROOT / 'cases/both_hands_no_signal/diagnostic-recipe.json', source)
    for path in source.iterdir():
        target = output / path.name
        if target.exists():
            raise ValueError('Diagnostic source shadows construction: ' + path.name)
        if path.is_dir():
            shutil.copytree(path, target)
        else:
            shutil.copy2(path, target)
print('both-hands source-complete diagnostic attempt materialized')
