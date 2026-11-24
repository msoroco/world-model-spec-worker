"""Prepare a current-runner synthetic short attempt for recorded-only proof."""

import argparse
import json
from pathlib import Path
import sys


WORK = Path(__file__).resolve().parent
REPO = WORK.parents[1]
sys.path[:0] = [str(REPO / 'runtime/scenario_pipeline'),
                str(REPO / 'runtime/python')]
from worker_exchange.common import within
from worker_exchange.fixture_recipe import materialize as materialize_fixture
from worker_exchange.runtime_cli import materialize as materialize_candidate
from worker_exchange.saved_processing import copy_sources


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', default='primary')
    parser.add_argument('--scratch', required=True)
    parser.add_argument('--manifest', default=str(WORK / 'current-runtime-runner-reference-bound-manifest.json'))
    args = parser.parse_args()
    scratch = Path(args.scratch).resolve()
    if REPO / '.runtime-work' not in scratch.parents:
        raise ValueError('Synthetic attempt belongs under .runtime-work')
    manifest = Path(args.manifest).resolve()
    if manifest.parent != WORK:
        raise ValueError('Current runner draft manifest must belong to this assignment')
    case_id = WORK.name + '__' + args.case
    matches = [item for item in json.loads(manifest.read_text())['cases']
               if item['case_id'] == case_id]
    if len(matches) != 1:
        raise ValueError('Exact current-runner case not selected')
    entry = matches[0]
    fixture = scratch / 'fixture'
    attempt = scratch / 'attempt'
    source = materialize_fixture(REPO, within(REPO, entry['fixture_recipe']), fixture)
    materialize_candidate(manifest, case_id, attempt, args.candidate)
    copy_sources(fixture, attempt)
    print(json.dumps({'case_id': case_id, 'candidate_id': args.candidate,
                      'attempt': str(attempt), 'fixture_sha256': source['fixture_sha256'],
                      'fixture_recipe_sha256': source['recipe_sha256']}, sort_keys=True))


if __name__ == '__main__':
    main()
