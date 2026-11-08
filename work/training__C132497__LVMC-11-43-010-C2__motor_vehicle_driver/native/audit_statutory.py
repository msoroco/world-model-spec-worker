"""Independently audit exact law-topic and synthetic evidence coverage."""
import hashlib
import json
from pathlib import Path

CASE=Path(__file__).resolve().parent.parent
ROOT=CASE.parents[1]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]

def audit():
    path=CASE/'statutory-review.json';review=json.loads(path.read_text())
    assignment=ROOT/'inputs'/CASE.name/'assignment.json'
    plan=CASE/'case-plan.json';source=json.loads(assignment.read_text())
    planned=json.loads(plan.read_text())
    if (review['format']!='c132497-statutory-review-v1' or
        review['law_id']!=source['law_id'] or
        review['exact_law_text']!=source['law_record']['text'] or
        {x['topic'] for x in review['topics']}!={'text-0','text-1','text-2'} or
        any(x['source_assignment_sha256']!=sha(assignment) or
            x['case_plan_sha256']!=sha(plan) or
            x['status']!='pending_original_evidence' or
            x['original_right_turn_observed'] or
            x['physical_roundabout_verified'] or
            x['legal_verdict'] is not None for x in review['topics']) or
        review['original_native_observed'] or review['delivery_ready']):
        raise ValueError('C132497 exact statutory review differs')
    for witness,lane in (('reference',-2),('contrast',-1)):
        bundle=CASE/'offline'/'bundles'/witness/'primary'
        observed=rows(bundle/'saved'/'native-observed.jsonl')
        item=review['synthetic_case_measurements'][witness]
        if (len(observed)!=240 or
            item['right_lane_used']!=(lane==-2) or
            item['phase_frames']!={phase:sum(x['phase']==phase for x in observed)
                for phase in ('entry','circulation','exit')} or
            any(x['lane_id']!=lane for x in observed)):
            raise ValueError('C132497 statutory saved mapping differs')
    receipt={'format':'c132497-independent-statutory-audit-v1',
        'review_sha256':sha(path),'topics_checked':3,
        'synthetic_cases_checked':2,'original_native_observed':False,
        'delivery_ready':False}
    (CASE/'statutory-audit.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

if __name__=='__main__':print(json.dumps(audit()))
