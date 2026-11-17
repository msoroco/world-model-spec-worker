"""Join a current short diagnostic recipe to its exact selected construction."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize as fixture_materialize
from worker_exchange.runtime_cli import materialize as package_materialize


def prepare(case, candidate):
    if case not in ('reference', 'contrast') or candidate not in (
            'primary', 'fallback1', 'fallback2', 'fallback3'):
        raise ValueError('Unsupported short selected candidate')
    private = REPO / '.runtime-work'
    stem = f'c150142-{case}-{candidate}-update037'
    fixture = private / (stem + '-fixture')
    attempt = private / (stem + '-saved-attempt')
    if fixture.exists() or attempt.exists():
        raise ValueError('Use a fresh short saved attempt')
    recipe = ROOT / 'selected-diagnostics' / case / (candidate + '-recipe.json')
    manifest = ROOT / ('execution-manifest-diagnostic-' + case + '.json')
    fixture_receipt = fixture_materialize(REPO, recipe, fixture)
    package_materialize(manifest, ROOT.name + '__' + case, attempt, candidate)
    for item in fixture.iterdir():
        target = attempt / item.name
        if target.exists():
            raise ValueError('Fixture shadows package: ' + item.name)
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
    return {'case_id': ROOT.name + '__' + case, 'candidate_id': candidate,
            'fixture_sha256': fixture_receipt['fixture_sha256'],
            'attempt': str(attempt), 'source_kind': 'synthetic_native_sample',
            'original_native_observed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.case, args.candidate), sort_keys=True))
