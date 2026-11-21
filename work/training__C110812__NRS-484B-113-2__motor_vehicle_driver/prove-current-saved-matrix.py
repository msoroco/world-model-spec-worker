"""Run the current recorded-only synthetic path for each exact draft candidate."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / 'runtime/pipeline'), str(ROOT / 'runtime/pipeline/scenario_pipeline')]
from scenario_pipeline.worker_exchange.fixture_recipe import materialize
from scenario_pipeline.worker_exchange.package_compatibility import materialize_case
from scenario_pipeline.worker_exchange.saved_processing import run


def prove(suffix, candidate):
    manifest = HERE / 'draft-execution-manifest.json'
    entry = next(e for e in json.loads(manifest.read_text())['cases']
                 if e['case_id'].endswith('__' + suffix))
    base = ROOT / '.runtime-work' / ('c110812-current-saved-' + suffix + '-' + candidate)
    fixture, attempt, output = (base / name for name in ('fixture', 'attempt', 'output'))
    if base.exists():
        raise ValueError('Use a fresh synthetic saved-processing workspace: ' + str(base))
    source = materialize(ROOT, ROOT / entry['fixture_recipe'], fixture)
    materialize_case(manifest, entry['case_id'], attempt, fixture, candidate)
    result = run(manifest, entry['case_id'], attempt, output,
                 ROOT / 'runtime/pipeline/library',
                 ROOT / '.runtime-work/c110812-current-decoder/.lake/build/bin/adapterCheck')
    if not result.get('passed') or not result.get('recorded_only') or result.get('missing_evidence'):
        raise ValueError('Recorded-only proof incomplete')
    summary = {'case_id': entry['case_id'], 'candidate_id': candidate,
               'fixture_recipe_sha256': source['recipe_sha256'],
               'fixture_sha256': source['fixture_sha256'],
               'passed': True, 'recorded_only': True,
               'saved_receipt': result}
    path = HERE / ('current-saved-' + suffix + '-' + candidate + '-receipt.json')
    path.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'case_id': entry['case_id'], 'candidate_id': candidate,
                      'passed': True, 'receipt': str(path)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--suffix', choices=('false', 'true'), required=True)
    parser.add_argument('--candidate', choices=('primary', 'fallback1', 'fallback2', 'fallback3'), required=True)
    args = parser.parse_args()
    prove(args.suffix, args.candidate)
