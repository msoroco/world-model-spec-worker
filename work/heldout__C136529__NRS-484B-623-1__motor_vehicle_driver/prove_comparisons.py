"""Materialize exact textual sources and exercise three independent comparisons."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
folder=Path(__file__).resolve().parent;repo=folder.parents[1]
sys.path.insert(0,str(folder));sys.path.insert(1,str(repo/'runtime/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize as make_fixture
from worker_exchange.runtime_cli import materialize as make_attempt
from worker_exchange.saved_processing import copy_sources
from comparison_audit import PAIRS,audit
parser=argparse.ArgumentParser();parser.add_argument('--comparison',required=True)
parser.add_argument('--negative',action='store_true');args=parser.parse_args()
if args.comparison not in PAIRS:raise ValueError('unknown comparison')
manifest=json.loads((folder/'execution-manifest.json').read_text())
work=repo/'.runtime-work';work.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='c136529-comparison-',dir=work) as temp:
    roots=[]
    for branch in PAIRS[args.comparison][:2]:
        case=folder.name+'__'+branch
        entry=next(e for e in manifest['cases'] if e['case_id']==case)
        fixture=Path(temp)/(branch+'-fixture')
        make_fixture(repo,repo/entry['fixture_recipe'],fixture)
        attempt=Path(temp)/(branch+'-attempt')
        make_attempt(folder/'execution-manifest.json',case,attempt)
        copy_sources(fixture,attempt)
        roots.append(attempt)
    if args.negative:
        second=roots[1]/'config.json';cfg=json.loads(second.read_text())
        cfg['duration_s']=9;second.write_text(json.dumps(cfg)+'\n')
    report=audit(args.comparison,*roots)
    assert report['comparison_id']==args.comparison
    assert report['physical_acceptance_claimed'] is False
    print(args.comparison,'comparison_audit_passed',report['declared_differences'])
