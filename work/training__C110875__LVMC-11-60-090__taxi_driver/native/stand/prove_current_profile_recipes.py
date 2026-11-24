"""Materialize both portable full-profile taxi source packets and remeasure."""
import hashlib
import json
from pathlib import Path
import sys

from saved import process

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    records=[]
    for case in ('probe_01','probe_02'):
        recipe=HERE/f'current-profile-{case}-recipe.json'
        source=ROOT/'.runtime-work/c110875-current-profile-recipes'/case
        if source.exists():raise ValueError('Use fresh diagnostic output')
        source.parent.mkdir(parents=True,exist_ok=True)
        manifest=materialize(ROOT,recipe,source)
        measured=process(HERE/'drafts'/case,source,synthetic=True)
        assert measured['frames']==600 and measured['turn_request_matched']
        assert measured['source_kind']=='synthetic_cpu' and not measured['delivery_ready']
        records.append({'case_id':measured['case_id'],'recipe_sha256':manifest['recipe_sha256'],
                        'fixture_sha256':manifest['fixture_sha256'],
                        'source_kind':measured['source_kind'],
                        'first_intersection_approach_frame':measured['first_intersection_approach_frame'],
                        'measured_first_turn':measured['measured_first_turn'],
                        'camera_sha256':measured['camera_sha256']})
    assert records[0]['first_intersection_approach_frame']==records[1]['first_intersection_approach_frame']==299
    assert [r['measured_first_turn'] for r in records]==['right','straight']
    proof={'format':'c110875-current-profile-recipe-proof-v1','passed':True,
           'records':records,'frames_per_case':600,'rate_hz':20,
           'synthetic_fixture':True,'native_executed':False,
           'stand_designation_established':False,'posted_notice_established':False,
           'taxi_license_established':False,'first_intersection_native_established':False,
           'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}
    path=HERE/'current-profile-recipe-proof.json'
    path.write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({'passed':True,'proof_sha256':sha(path),
                      'cases':len(records),'frames_per_case':600}))

if __name__=='__main__':main()
