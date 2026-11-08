"""Map exact LVMC counterclockwise clause to both planned witnesses."""
import hashlib
import json
from pathlib import Path

CASE=Path(__file__).resolve().parent
ROOT=CASE.parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    source_path=ROOT/'inputs'/CASE.name/'assignment.json'
    plan_path=CASE/'case-plan.json'
    manifest_path=CASE/'native'/'drafts'/'manifest.json'
    source=json.loads(source_path.read_text())
    plan=json.loads(plan_path.read_text())
    manifest=json.loads(manifest_path.read_text())
    saved_path=CASE/'native'/'saved-proof.json'
    saved=json.loads(saved_path.read_text())
    measured={row['witness']:row['measurement'] for row in saved['positives']}
    if source['law_id']!='LVMC-11-43-010-A' or len(plan['cases'])!=2:
        raise ValueError('LVMC statutory scope differs')
    rows=[]
    for item in plan['cases']:
        witness=item['case_id'].removeprefix(CASE.name+'__')
        expected='counterclockwise' if witness=='witness_1' else 'clockwise'
        sample=measured[witness]
        if sample['source_kind']!='synthetic_cpu' or sample['frames']!=240:
            raise ValueError('LVMC synthetic saved source differs')
        rows.append({'case_id':item['case_id'],'witness':witness,
            'source_law_sha256':source['local_snapshot']['law_sha256'],
            'assignment_sha256':sha(source_path),
            'case_plan_sha256':sha(plan_path),
            'construction_manifest_sha256':sha(manifest_path),
            'statutory_text':source['law_record']['text'],
            'activation':'subject vehicle within a physically verified roundabout',
            'requirement':'all vehicular travel counterclockwise',
            'requested_rotation':expected,
            'synthetic_measurement_sha256':sha(saved_path),
            'synthetic_signed_angular_progress_rad':sample['signed_angular_progress_rad'],
            'synthetic_requested_rotation_frames':sample['rotation_frame_counts'][expected],
            'synthetic_authored_ring_frames':sample['occupied_authored_ring_frames'],
            'measured_rotation':None,'roundabout_verified':False,
            'accepted_original_equivalence':False,
            'legal_verdict':None,'status':'pending_original_evidence'})
    result={'format':'c234827-lvmc-statutory-review-v1',
        'assignment_id':CASE.name,'rows':rows,
        'accepted_memberships_replayed':0,'delivery_ready':False}
    (CASE/'statutory-review.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':print(json.dumps({'rows':len(build()['rows'])}))
