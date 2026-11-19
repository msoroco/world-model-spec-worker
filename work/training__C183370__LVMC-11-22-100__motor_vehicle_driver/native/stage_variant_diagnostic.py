"""Stage only inventoried barrier diagnostic acquisition for saved processing."""
import argparse
import json
import shutil
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.fixture_generator import inspect
from worker_exchange.runtime_cli import materialize


def stage(route, compatibility, target):
    if route not in ('crossing', 'avoidance'):
        raise ValueError('Unknown barrier route')
    case = PACKAGE.name + '__barrier_' + route
    manifest = PACKAGE / 'draft-barrier-capture-manifest.json'
    source, target = Path(compatibility).resolve(), Path(target).resolve()
    receipt = json.loads((source / 'compatibility.json').read_text())
    if (receipt.get('passed') is not True or receipt.get('candidate_id') != 'primary'
            or receipt.get('case_id') != case):
        raise ValueError('Compatibility proof differs from barrier primary')
    spec = json.loads((PACKAGE / 'variant-diagnostics/barrier' / route / 'primary.json').read_text())
    materialize(manifest, case, target, 'primary')
    for relative in inspect(spec):
        original, destination = source / relative, target / relative
        if not original.is_file() or destination.exists():
            raise ValueError('Diagnostic source missing or shadows construction: ' + relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, destination)
    return len(inspect(spec))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--route', required=True)
    parser.add_argument('--compatibility', required=True)
    parser.add_argument('--target', required=True)
    args = parser.parse_args()
    print(stage(args.route, args.compatibility, args.target))
