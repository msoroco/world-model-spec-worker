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


def stage(route, compatibility, target, candidate='primary', manifest=None):
    if route not in ('crossing', 'avoidance'):
        raise ValueError('Unknown barrier route')
    case = PACKAGE.name + '__barrier_' + route
    manifest = Path(manifest) if manifest is not None else PACKAGE / 'draft-barrier-capture-manifest.json'
    source, target = Path(compatibility).resolve(), Path(target).resolve()
    receipt = json.loads((source / 'compatibility.json').read_text())
    if (receipt.get('passed') is not True or receipt.get('candidate_id') != candidate
            or receipt.get('case_id') != case):
        raise ValueError('Compatibility proof differs from barrier candidate')
    document = json.loads(manifest.read_text())
    entry = next((row for row in document['cases'] if row['case_id'] == case), None)
    if entry is None:
        raise ValueError('Barrier case absent from selected manifest')
    selected = entry if candidate == 'primary' else next(
        (row for row in entry['candidates'] if row['id'] == candidate), None)
    if selected is None or receipt.get('construction_sha256') != selected['construction_sha256']:
        raise ValueError('Compatibility construction differs from selected manifest')
    spec = json.loads((PACKAGE / 'variant-diagnostics/barrier' / route / 'primary.json').read_text())
    materialize(manifest, case, target, candidate)
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
    parser.add_argument('--candidate', default='primary')
    parser.add_argument('--compatibility', required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--manifest')
    args = parser.parse_args()
    print(stage(args.route, args.compatibility, args.target, args.candidate,
                args.manifest))
