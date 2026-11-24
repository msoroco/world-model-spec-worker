"""Materialize a source-bound unselected parking acquisition for saved processing."""
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
    parser.add_argument('--case', choices=('witness_1','witness_2'),default='witness_1')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if ROOT / '.runtime-work' not in output.parents:
        raise ValueError('Attempt must be under .runtime-work')
    output.parent.mkdir(parents=True, exist_ok=True)
    fixture = output.parent / (output.name + '-fixture')
    recipe = HERE / f'current-v2-{args.case}-recipe.json'
    source = make_fixture(ROOT, recipe, fixture)
    manifest = HERE / 'current-v2-probe-manifest.json'
    case = HERE.name + '__' + args.case
    make_construction(manifest, case, output, 'primary')
    copy_sources(fixture, output)
    (output / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
        'native_executed': False, 'original_pixels_reviewed': False,
    }, indent=2) + '\n')
    print(json.dumps({'case_id': case, 'recipe_sha256': source['recipe_sha256'],
                      'fixture_sha256': source['fixture_sha256'], 'attempt': str(output)}))

if __name__ == '__main__':
    main()
