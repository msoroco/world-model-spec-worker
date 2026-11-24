"""Stage a source-hashed diagnostic acquisition for public saved processing."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize as make_fixture
from worker_exchange.runtime_cli import materialize as make_construction
from worker_exchange.saved_processing import copy_sources


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('witness_1', 'witness_2'), required=True)
    parser.add_argument('--candidate', choices=('primary', 'fallback1', 'fallback2', 'fallback3'), default='primary')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    destination = args.output.resolve()
    if ROOT / '.runtime-work' not in destination.parents:
        raise ValueError('Diagnostic attempt must be under .runtime-work')
    destination.parent.mkdir(parents=True, exist_ok=True)
    fixture = destination.parent / (destination.name + '-fixture')
    recipe = HERE / f'v2-{args.case}-recipe.json'
    source = make_fixture(ROOT, recipe, fixture)
    manifest = HERE / 'current-v2-probe-manifest.json'
    case_id = HERE.name + '__' + args.case
    make_construction(manifest, case_id, destination, args.candidate)
    copy_sources(fixture, destination)
    (destination / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
        'native_executed': False, 'original_pixels_reviewed': False,
    }, indent=2) + '\n')
    print(json.dumps({'case_id': case_id, 'candidate_id': args.candidate,
                      'fixture_sha256': source['fixture_sha256'],
                      'fixture_recipe_sha256': source['recipe_sha256'],
                      'attempt': str(destination)}))


if __name__ == '__main__':
    main()
