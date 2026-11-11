"""Positive source audit plus required missing-participant rejection."""
import argparse,json,sys,tempfile
from pathlib import Path
folder=Path(__file__).resolve().parent;repo=folder.parents[1]
sys.path.insert(0,str(folder));sys.path.insert(1,str(repo/'runtime/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize as make_fixture
from worker_exchange.runtime_cli import materialize as make_attempt
from worker_exchange.saved_processing import copy_sources
from signal_finalizer import analyze
from delivery_audit import audit_attempt

parser=argparse.ArgumentParser();parser.add_argument('--case',required=True)
parser.add_argument('--negative',action='store_true');args=parser.parse_args()
manifest=json.loads((folder/'execution-manifest.json').read_text())
entry=next((e for e in manifest['cases'] if e['case_id']==args.case),None)
if entry is None:raise ValueError('unknown exact case')
with tempfile.TemporaryDirectory(prefix='c111273-audit-',dir=repo/'.runtime-work') as temp:
    base=Path(temp);fixture=base/'fixture'
    make_fixture(repo,repo/entry['fixture_recipe'],fixture)
    attempt=base/'attempt';make_attempt(folder/'execution-manifest.json',args.case,attempt)
    copy_sources(fixture,attempt)
    report=analyze(attempt,write_channels=False)
    if args.negative:(attempt/'participant_state.jsonl').unlink()
    result=audit_attempt(attempt,report,args.case,receipt_dir=base/'decodes')
    assert result['frame_count']==9 and len(result['camera_decodes'])==4
    assert result['physical_acceptance_claimed'] is False
    print(args.case,'source_audit_prepared',result['frame_count'])
