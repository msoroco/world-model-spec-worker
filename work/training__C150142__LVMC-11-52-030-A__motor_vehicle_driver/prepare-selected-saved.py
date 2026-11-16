"""Materialize a fresh synthetic acquisition for the pinned saved-only command."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
sys.path.insert(0,str(REPO/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize
from worker_exchange.fixture_recipe import materialize as fixture_materialize
from worker_exchange.saved_processing import copy_sources


def prepare(attempt, fixture, candidate='primary'):
    attempt,fixture=Path(attempt).resolve(),Path(fixture).resolve()
    private=(REPO/'.runtime-work').resolve()
    if private not in attempt.parents or private not in fixture.parents or \
       attempt==fixture:
        raise ValueError('Synthetic attempt and fixture belong in separate .runtime-work paths')
    if candidate not in ('primary','fallback1','fallback2','fallback3'):
        raise ValueError('Unknown exact candidate')
    manifest=ROOT/('execution-manifest-diagnostic-reference.json' if candidate=='primary'
        else 'execution-manifest-diagnostic-reference-'+candidate+'.json')
    case=ROOT.name+'__reference'
    entry=next(item for item in json.loads(manifest.read_text())['cases']
               if item['case_id']==case)
    materialize(manifest,case,attempt,candidate)
    source=fixture_materialize(REPO,REPO/entry['fixture_recipe'],fixture)
    copy_sources(fixture,attempt)
    return {'case_id':case,'candidate_id':candidate,'attempt':str(attempt),
            'fixture':str(fixture),'fixture_sha256':source['fixture_sha256'],
            'source_kind':'synthetic_native_sample','original_native_observed':False}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--attempt',required=True)
    p.add_argument('--fixture',required=True)
    p.add_argument('--candidate',default='primary')
    a=p.parse_args()
    print(json.dumps(prepare(a.attempt,a.fixture,a.candidate),sort_keys=True))
