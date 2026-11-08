"""Independent frozen-source and six-row one-way statutory coverage audit."""
import hashlib
import json
from pathlib import Path

CASE=Path(__file__).resolve().parent
ROOT=CASE.parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    path=CASE/'statutory-review.json';review=json.loads(path.read_text())
    files={'assignment_sha256':ROOT/'inputs'/CASE.name/'assignment.json',
           'branch_source_sha256':ROOT/'inputs/coverage/branch-sources.json',
           'case_plan_sha256':CASE/'case-plan.json',
           'construction_manifest_sha256':CASE/'native/drafts/manifest.json'}
    files['saved_proof_sha256']=CASE/'native/saved-proof.json'
    if (review['format']!='c150916-statutory-review-v1' or
            review['assignment_id']!=CASE.name or
            any(review[key]!=sha(value) for key,value in files.items()) or
            review['topic_count']!=3 or len(review['candidate_topic_rows'])!=6 or
            any(review[key] for key in ('original_native_observed','legal_coverage_ready','delivery_ready'))):
        raise ValueError('One-way statutory source, status or coverage differs')
    source=json.loads(files['branch_source_sha256'].read_text())['laws']['NRS-484B-220-1']
    assignment=json.loads(files['assignment_sha256'].read_text())
    plan=json.loads(files['case_plan_sha256'].read_text())
    if source['law']['text']!=assignment['law_record']['text']:
        raise ValueError('One-way frozen law text differs')
    topics=source['topics'];cases={row['case_id']:row for row in plan['cases']}
    expected={(topic,case) for topic in topics for case in cases};seen=set()
    for row in review['candidate_topic_rows']:
        key=row['topic_id'],row['case_id']
        if key not in expected or key in seen:raise ValueError('One-way topic row differs')
        seen.add(key)
        topic=topics[row['topic_id']]
        if (row['topic_kind']!=topic['kind'] or row['topic_text']!=topic['text'] or
                row['requested_direction']!=cases[row['case_id']]['requested_setting'] or
                row['requested_sign_type']!='R6-1' or len(row['required_original_evidence'])!=5 or
                row['status']!='pending_original_authority_and_judgment' or
                row['designation_authority_verified'] or row['physical_sign_verified'] or
                row['legal_verdict'] is not None):
            raise ValueError('One-way statutory fact or status differs')
        case=row['requested_direction']
        actor=CASE/'native/saved-fixtures'/case/'native-observed.jsonl'
        observed=[json.loads(line) for line in actor.read_text().splitlines()]
        sign=CASE/'native/saved-fixtures'/case/'sign-frames.jsonl'
        sign_rows=[json.loads(line) for line in sign.read_text().splitlines()]
        visible={str(sign_id):sum(sign_id in frame['visible_sign_ids'] for frame in sign_rows)
                 for sign_id in (101,102)}
        displacement=round(observed[-1]['ego_x_m']-observed[0]['ego_x_m'],3)
        if (len(observed)!=240 or len(sign_rows)!=240 or row['saved_actor_sha256']!=sha(actor) or
                row['synthetic_signed_displacement_m']!=displacement or
                row['synthetic_direction_matches_designation']!=(displacement>0) or
                row['synthetic_visible_sign_frames']!=visible):
            raise ValueError('One-way statutory saved measurement differs')
    if seen!=expected:raise ValueError('One-way topic coverage incomplete')
    receipt={'format':'c150916-independent-statutory-audit-v1',
             'review_sha256':sha(path),'topics_checked':3,'rows_checked':6,
             'original_native_observed':False,'legal_coverage_ready':False,
             'delivery_ready':False}
    (CASE/'statutory-review-audit.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':print(json.dumps(audit()))
