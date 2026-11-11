"""Make a fresh materialized construction with explicit diagnostic originals."""
import argparse
from pathlib import Path
import shutil
import tempfile

from worker_exchange.runtime_cli import materialize
from worker_exchange.fixture_recipe import materialize as materialize_fixture

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PREFIX = 'heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator__'

parser = argparse.ArgumentParser()
parser.add_argument('--slug', choices=['safety_wide', 'safety_narrow'], required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args()
manifest = ROOT / (args.slug.replace('_', '-') + '-manifest.json')
recipe = ROOT / 'cases' / args.slug / 'diagnostic-recipe.json'
output = Path(args.output).resolve()
materialize(manifest, PREFIX + args.slug, output)
with tempfile.TemporaryDirectory(prefix='rider-safety-sources-', dir=REPO / '.runtime-work') as tmp:
    source = Path(tmp) / 'fixture'
    materialize_fixture(REPO, recipe, source)
    for path in source.iterdir():
        target = output / path.name
        if target.exists():
            raise ValueError('Diagnostic source shadows construction: ' + path.name)
        if path.is_dir():
            shutil.copytree(path, target)
        else:
            shutil.copy2(path, target)
print(args.slug, 'materialized source-complete diagnostic attempt', output)
