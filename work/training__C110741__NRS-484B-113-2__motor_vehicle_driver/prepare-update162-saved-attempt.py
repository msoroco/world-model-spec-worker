"""Create a fresh selected synthetic attempt for recorded-only CPU processing."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / 'runtime/pipeline'),
                str(ROOT / 'runtime/pipeline/scenario_pipeline')]
from scenario_pipeline.worker_exchange.fixture_recipe import materialize
from scenario_pipeline.worker_exchange.package_compatibility import materialize_case


def prepare(suffix, revision, candidate):
    manifest = HERE / 'execution-manifest.json'
    entry = next(item for item in json.loads(manifest.read_text())['cases']
                 if item['case_id'].endswith('__condition_' + suffix))
    base = ROOT / '.runtime-work' / ('c110741-update162-' + suffix + '-' + candidate + '-saved-' + revision)
    fixture = base / 'fixture'
    attempt = base / 'attempt'
    source = materialize(ROOT, ROOT / entry['fixture_recipe'], fixture)
    materialize_case(manifest, entry['case_id'], attempt, fixture, candidate)
    return {'case_id': entry['case_id'], 'attempt': str(attempt),
            'fixture_recipe_sha256': source['recipe_sha256'],
            'fixture_sha256': source['fixture_sha256']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--suffix', choices=('a', 'b'), required=True)
    parser.add_argument('--revision', default='final')
    parser.add_argument('--candidate', choices=('primary','fallback1','fallback2','fallback3'), default='primary')
    args = parser.parse_args()
    print(json.dumps(prepare(args.suffix, args.revision, args.candidate), indent=2))
