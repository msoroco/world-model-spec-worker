"""Exercise independent source audit on a labelled diagnostic capture."""
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
from one_way_saved import analyze
from delivery_audit import audit_attempt

parser = argparse.ArgumentParser()
parser.add_argument('--case', required=True)
parser.add_argument('--negative', action='store_true')
args = parser.parse_args()
manifest = json.loads((folder/'execution-manifest.json').read_text())
entry = next((e for e in manifest['cases'] if e['case_id'] == args.case), None)
if entry is None: raise ValueError('Unknown exact case')
with tempfile.TemporaryDirectory(prefix='c152976-audit-', dir=repo/'.runtime-work') as temp:
    base = Path(temp)
    fixture = base/'fixture'
    make_fixture(repo, repo/entry['fixture_recipe'], fixture)
    attempt = base/'attempt'
    make_attempt(folder/'execution-manifest.json', args.case, attempt)
    copy_sources(fixture, attempt)
    report = analyze(attempt)
    if args.negative: (attempt/'native/road_edges.jsonl').unlink()
    audited = audit_attempt(attempt, report, args.case, receipt_dir=base/'decodes')
    assert audited['frame_count'] > 0 and len(audited['camera_decodes']) == 4
    assert audited['physical_acceptance_claimed'] is False
    print(args.case, 'independent_source_audit_passed')
