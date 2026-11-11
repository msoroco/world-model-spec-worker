"""Materialize fresh source-complete electric-device CPU diagnostic attempts."""
import argparse
from pathlib import Path
import shutil
import tempfile
from worker_exchange.runtime_cli import materialize
from worker_exchange.fixture_recipe import materialize as materialize_fixture

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--device', choices=('electric_bicycle','electric_scooter'), required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args()
case = 'heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator__' + args.device + '_signal_once'
output = Path(args.output).resolve()
materialize(ROOT / (args.device.replace('_', '-') + '-manifest.json'), case, output)
with tempfile.TemporaryDirectory(prefix='rider-electric-sources-', dir=REPO / '.runtime-work') as temporary:
    source = Path(temporary) / 'fixture'
    materialize_fixture(REPO, ROOT / 'cases' / (args.device + '_signal_once') / 'diagnostic-recipe.json', source)
    for path in source.iterdir():
        target = output / path.name
        if target.exists():
            raise ValueError('Diagnostic source shadows construction: ' + path.name)
        if path.is_dir():
            shutil.copytree(path, target)
        else:
            shutil.copy2(path, target)
print(case, 'source-complete synthetic attempt')
