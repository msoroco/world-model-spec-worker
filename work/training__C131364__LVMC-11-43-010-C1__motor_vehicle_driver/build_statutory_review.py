"""Map the exact C131364 lane clause to synthetic requests and pending exits."""
import hashlib
import json
from pathlib import Path

CASE=Path(__file__).resolve().parent
ROOT=CASE.parents[1]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def build():
    source_path=ROOT/'inputs'/CASE.name/'assignment.json'
    plan_path=CASE/'case-plan.json'
    saved_path=CASE/'native'/'saved-proof.json'
    source=json.loads(source_path.read_text())
    plan=json.loads(plan_path.read_text())
    saved=json.loads(saved_path.read_text())
    measurements={row['witness']:row['measurement'] for row in saved['positives']}
    if source['law_id']!='LVMC-11-43-010-C1' or len(plan['cases'])!=2:
        raise ValueError('C131364 statutory scope differs')
    rows=[]
    for item in plan['cases']:
        witness=item['case_id'].removeprefix(CASE.name+'__')
        sample=measurements[witness]
        if sample['source_kind']!='synthetic_cpu' or sample['actual_left_exit_observed']:
            raise ValueError('C131364 synthetic source overclaims')
        rows.append({'case_id':item['case_id'],'witness':witness,
                     'assignment_sha256':sha(source_path),'case_plan_sha256':sha(plan_path),
                     'source_law_sha256':source['local_snapshot']['law_sha256'],
                     'statutory_text':source['law_record']['text'],
                     'activation':'physical multi-lane roundabout and actual left or U-turn exit',
                     'requirement':'use left circulating lane',
                     'synthetic_measurement_proof_sha256':sha(saved_path),
                     'synthetic_requested_lane_id':sample['requested_lane_id'],
                     'synthetic_full_body_lane_frames':sample['full_body_requested_lane_frames'],
                     'original_lane_measurement':None,
                     'actual_left_exit_observed':False,'roundabout_verified':False,
                     'legal_verdict':None,'status':'pending_original_evidence'})
    result={'format':'c131364-statutory-review-v1','assignment_id':CASE.name,
            'rows':rows,'accepted_memberships_replayed':0,'delivery_ready':False}
    (CASE/'statutory-review.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps({'rows':len(build()['rows'])}))
