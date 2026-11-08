"""Independently audit exact LVMC clause and pending witness coverage."""
import hashlib
import json
from pathlib import Path

CASE=Path(__file__).resolve().parent
ROOT=CASE.parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    source_path=ROOT/'inputs'/CASE.name/'assignment.json'
    plan_path=CASE/'case-plan.json'
    manifest_path=CASE/'native'/'drafts'/'manifest.json'
    review_path=CASE/'statutory-review.json'
    source=json.loads(source_path.read_text())
    plan=json.loads(plan_path.read_text())
    review=json.loads(review_path.read_text())
    text='The following regulations pertain to the operation of vehicles within a roundabout: All vehicular travel shall be in a counterclockwise direction.'
    if (source['law_record']['text']!=text or
            review['format']!='c234827-lvmc-statutory-review-v1' or
            review['assignment_id']!=CASE.name or
            len(review['rows'])!=2 or review['accepted_memberships_replayed']!=0 or
            review['delivery_ready']):
        raise ValueError('LVMC statutory review scope differs')
    expected={row['case_id'] for row in plan['cases']}
    if {row['case_id'] for row in review['rows']}!=expected:
        raise ValueError('LVMC witness statutory coverage differs')
    for row in review['rows']:
        witness=row['case_id'].removeprefix(CASE.name+'__')
        if (row['witness']!=witness or
                row['source_law_sha256']!=source['local_snapshot']['law_sha256'] or
                row['assignment_sha256']!=sha(source_path) or
                row['case_plan_sha256']!=sha(plan_path) or
                row['construction_manifest_sha256']!=sha(manifest_path) or
                row['statutory_text']!=text or
                row['requested_rotation']!=
                ('counterclockwise' if witness=='witness_1' else 'clockwise') or
                row['measured_rotation'] is not None or row['roundabout_verified'] or
                row['accepted_original_equivalence'] or row['legal_verdict'] is not None or
                row['status']!='pending_original_evidence'):
            raise ValueError('LVMC statutory row overclaims evidence')
    result={'format':'c234827-lvmc-independent-statutory-audit-v1',
        'review_sha256':sha(review_path),'rows_checked':2,
        'accepted_originals_replayed':0,'delivery_ready':False}
    (CASE/'statutory-review-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':print(json.dumps(audit()))
