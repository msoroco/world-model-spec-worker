"""Independent exact-case preflight for proposed Native bicycle construction."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

FOLDER=Path(__file__).resolve().parent
NATIVE=FOLDER/'native'
sys.path.insert(0,str(NATIVE))
from runner import check
from engineering import CANDIDATES,parameters

def main():
    plan=json.loads((FOLDER/'case-plan.json').read_text())
    assert [row['case_id'].split('__')[-1] for row in plan['cases']]==['witness_1','witness_2']
    outputs=[];hashes={}
    for case in ('witness_1','witness_2'):
        for candidate in CANDIDATES:
            result=check(case,candidate)
            assert result['passed'] and not result['native_imported'] and not result['physical_or_legal_outcome_claimed']
            knobs=parameters(case,candidate)['knobs']
            digest=hashlib.sha256(json.dumps(knobs,sort_keys=True).encode()).hexdigest()
            hashes.setdefault(case,set()).add(digest)
            outputs.append({'case':case,'candidate':candidate,'knob_sha256':digest})
    assert all(len(items)==4 for items in hashes.values())
    assert len({(row['case'],row['candidate']) for row in outputs})==8
    print(json.dumps({'passed':True,'exact_case_candidate_preflights':outputs,
        'distinct_knobs_per_case':4,'carla_run_or_physical_success_claimed':False},sort_keys=True))

if __name__=='__main__':main()
