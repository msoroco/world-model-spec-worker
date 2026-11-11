"""Exercise source-bound fixed-condition comparisons and a negative mutation."""
import argparse,json,sys,tempfile
from pathlib import Path
folder=Path(__file__).resolve().parent;repo=folder.parents[1]
sys.path.insert(0,str(folder));sys.path.insert(1,str(repo/'runtime/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize as make_fixture
from worker_exchange.runtime_cli import materialize as make_attempt
from worker_exchange.saved_processing import copy_sources
from signal_comparison_audit import PAIRS,audit

parser=argparse.ArgumentParser();parser.add_argument('--comparison',required=True)
parser.add_argument('--negative',action='store_true');args=parser.parse_args()
if args.comparison not in PAIRS:raise ValueError('unknown exact comparison')
manifest=json.loads((folder/'execution-manifest.json').read_text())
with tempfile.TemporaryDirectory(prefix='c111273-compare-',dir=repo/'.runtime-work') as temp:
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
    print(args.comparison,'fixed_and_changed_conditions_checked',report['deliberate_differences'])
