"""Exercise controlled comparisons on labelled diagnostic original sources."""
import argparse
import json
import sys
import tempfile
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parents[1]
sys.path.insert(0, str(folder))
sys.path.insert(1, str(repo/'runtime/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize as make_fixture
from worker_exchange.runtime_cli import materialize as make_attempt
from worker_exchange.saved_processing import copy_sources
from one_way_comparison_audit import audit, PAIRS

parser = argparse.ArgumentParser()
parser.add_argument('--comparison', required=True, choices=PAIRS)
parser.add_argument('--negative', action='store_true')
args = parser.parse_args()
manifest = json.loads((folder/'execution-manifest.json').read_text())
branches = PAIRS[args.comparison][:2]
with tempfile.TemporaryDirectory(prefix='c152976-comparison-', dir=repo/'.runtime-work') as temp:
    roots = []
    for branch in branches:
        case = next(e for e in manifest['cases'] if e['case_id'].endswith('__'+branch))
        fixture = Path(temp)/(branch+'-fixture')
        make_fixture(repo, repo/case['fixture_recipe'], fixture)
        attempt = Path(temp)/(branch+'-attempt')
        make_attempt(folder/'execution-manifest.json', case['case_id'], attempt)
        copy_sources(fixture, attempt)
        roots.append(attempt)
    if args.negative:
        path = roots[1]/'config.json'
        cfg = json.loads(path.read_text())
        cfg['target_speed_mps'] += 1
        path.write_text(json.dumps(cfg, indent=2)+'\n')
    result = audit(args.comparison, *roots)
    assert result['declared_difference_checked'] and result['fixed_conditions_checked']
    print(args.comparison, 'controlled_comparison_passed')
