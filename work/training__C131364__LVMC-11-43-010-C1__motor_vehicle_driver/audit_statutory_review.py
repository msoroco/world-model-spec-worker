"""Independently audit exact C131364 statutory and synthetic measurement joins."""
import hashlib
import json
from pathlib import Path

CASE=Path(__file__).resolve().parent
ROOT=CASE.parents[1]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def audit():
    source_path=ROOT/'inputs'/CASE.name/'assignment.json'
    plan_path=CASE/'case-plan.json'
    saved_path=CASE/'native'/'saved-proof.json'
    review_path=CASE/'statutory-review.json'
    source=json.loads(source_path.read_text())
    plan=json.loads(plan_path.read_text())
    saved=json.loads(saved_path.read_text())
    review=json.loads(review_path.read_text())
    text='The following regulations pertain to the operation of vehicles within a roundabout: The operator of a vehicle who intends to exit a roundabout: Shall use the left lane to turn left or complete a U-turn.'
    if (source['law_record']['text']!=text or
        review['format']!='c131364-statutory-review-v1' or len(review['rows'])!=2 or
        review['accepted_memberships_replayed']!=0 or review['delivery_ready']):
        raise ValueError('C131364 statutory clause coverage differs')
    expected={item['case_id'] for item in plan['cases']}
    if {row['case_id'] for row in review['rows']}!=expected:
        raise ValueError('C131364 statutory witness coverage differs')
    measured={row['witness']:row['measurement'] for row in saved['positives']}
    for row in review['rows']:
        witness=row['witness'];sample=measured[witness]
        if (row['assignment_sha256']!=sha(source_path) or
            row['case_plan_sha256']!=sha(plan_path) or
            row['source_law_sha256']!=source['local_snapshot']['law_sha256'] or
            row['statutory_text']!=text or
            row['synthetic_measurement_proof_sha256']!=sha(saved_path) or
            row['synthetic_requested_lane_id']!=sample['requested_lane_id'] or
            row['synthetic_full_body_lane_frames']!=sample['full_body_requested_lane_frames'] or
            row['original_lane_measurement'] is not None or
            row['actual_left_exit_observed'] or row['roundabout_verified'] or
            row['legal_verdict'] is not None or row['status']!='pending_original_evidence'):
            raise ValueError('C131364 statutory row overclaims')
    result={'format':'c131364-independent-statutory-audit-v1',
            'review_sha256':sha(review_path),'rows_checked':2,
            'actual_left_exit_observed':False,'delivery_ready':False}
    (CASE/'statutory-review-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(audit()))
