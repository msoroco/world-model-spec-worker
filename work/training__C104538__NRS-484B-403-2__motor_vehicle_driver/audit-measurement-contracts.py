"""Independent source/requirement and paired-output audit of draft contracts."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.measurement_contract import validate


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    plan=json.loads((HERE/'case-plan.json').read_text())
    source=json.loads((ROOT/'inputs'/HERE.name/'assignment.json').read_text())
    if plan['law_id']!='NRS-484B-403-2' or source['law_id']!=plan['law_id']:
        raise ValueError('Frozen law identity mismatch')
    code=(HERE/'native/finalize.py').read_text()
    rows=[]
    for suffix,fixture_name,expected in (('witness_1','straight',False),('witness_2','u_turn',True)):
        case_id=HERE.name+'__'+suffix
        contract_path=HERE/('draft-measurement-contract-'+suffix+'.json')
        contract=json.loads(contract_path.read_text())
        validate(contract,plan['requirement_dispositions'],code,case_id)
        if contract['case_id']!=case_id or contract['negative']['remove']!=['native_samples.jsonl']:
            raise ValueError('Case or negative contract mismatch')
        fixture=HERE/'draft-u-turn-saved'/fixture_name
        receipt=json.loads((fixture/'measurement.json').read_text())
        if receipt['u_turn_within_governed_region_observed'] is not expected:
            raise ValueError('Controlled pair measurement mismatch')
        if any(receipt['source_hashes'][name]!=sha(fixture/name) for name in
               ('native_samples.jsonl','video_frames.jsonl','sign-review.json','approach-video-fixture.txt')):
            raise ValueError('Saved source hash mismatch')
        rows.append({'case_id':case_id,'contract_sha256':sha(contract_path),
                     'measurement_sha256':sha(fixture/'measurement.json'),'observed_u_turn':expected})
    return {'passed':True,'records':rows,'source_identity_checked':True,
            'synthetic_only':True,'selected':False}


if __name__=='__main__':print(json.dumps(run(),indent=2))
