"""Prove the unselected 4 m/s draft's saved-source finalizer on CPU fixtures.

The input is a synthetic Native-shaped recipe. This is a source/procedure check,
not a physical or legal acceptance receipt or a canonical compatibility proof.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize as materialize_recipe
from worker_exchange.runtime_cli import materialize as materialize_construction, execution_env
from worker_exchange.saved_processing import copy_sources
from worker_exchange.common import digest, tree

CASE = HERE.name + '__yield_nearest_view_mid_speed'
MANIFEST = HERE / 'mid-speed-draft-manifest.json'
RECIPE = HERE / 'cases/through_mid/diagnostic-recipe.json'
BASE = REPO / '.runtime-work/c158190-mid-sources-v1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_finalizer(folder):
    return subprocess.run(
        [sys.executable, str(folder / 'finalizer.py'), '--attempt', str(folder),
         '--output', str(folder / 'analysis-report.json')],
        cwd=folder, env=execution_env(), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)


def prepare(folder, fixture):
    materialize_construction(MANIFEST, CASE, folder)
    copy_sources(fixture, folder)


def main():
    if BASE.exists():
        raise ValueError('Retain prior source proof; choose a fresh output name')
    BASE.mkdir(parents=True)
    fixture = BASE / 'fixture'
    materialize_recipe(REPO, RECIPE, fixture)
    positive = BASE / 'positive'
    prepare(positive, fixture)
    source_hash = digest(tree(positive / 'capture'))
    original_hashes = {name: sha(positive / name) for name in
                       ('approach_history.jsonl', 'visibility_rays.jsonl',
                        'interaction_history.jsonl', 'trace.jsonl',
                        'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                        'driver_reference.mkv')}
    result = run_finalizer(positive)
    (HERE / 'cases/through_mid/source-positive-current.log').write_text(result.stdout)
    if result.returncode:
        raise ValueError(f'Positive finalizer exited {result.returncode}')
    if digest(tree(positive / 'capture')) != source_hash:
        raise ValueError('Finalizer rewrote original Native capture')
    if any(sha(positive / name) != expected for name, expected in original_hashes.items()):
        raise ValueError('Finalizer rewrote original source')
    report = json.loads((positive / 'analysis-report.json').read_text())
    measurement = report['measurements']['speed_at_closest_view_mps']['value']
    if measurement != 4.0 or report['case_id'] != CASE:
        raise ValueError('Draft saved measurement is not the selected 4 m/s case')
    negative = BASE / 'negative'
    prepare(negative, fixture)
    (negative / 'visibility_rays.jsonl').unlink()
    failure = run_finalizer(negative)
    (HERE / 'cases/through_mid/source-negative-current.log').write_text(failure.stdout)
    if failure.returncode == 0 or 'Missing required source: visibility_rays.jsonl' not in failure.stdout:
        raise ValueError('Missing original sight rays were not rejected')
    receipt = {
        'format': 'c158190-unselected-source-finalizer-diagnostic',
        'case_id': CASE,
        'physical_acceptance_claimed': False,
        'canonical_compatibility_claimed': False,
        'recipe_sha256': sha(RECIPE),
        'construction_sha256': sha(HERE / 'cases/through_mid/construction.json'),
        'fixture_source_count': len(json.loads(RECIPE.read_text())['sources']),
        'positive_measurement_mps': measurement,
        'negative_removed_source': 'visibility_rays.jsonl',
        'negative_exit_code': failure.returncode,
        'positive_analysis_sha256': sha(positive / 'analysis-report.json'),
        'positive_log_sha256': sha(HERE / 'cases/through_mid/source-positive-current.log'),
        'negative_log_sha256': sha(HERE / 'cases/through_mid/source-negative-current.log'),
    }
    path = HERE / 'cases/through_mid/source-finalizer-diagnostic.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
