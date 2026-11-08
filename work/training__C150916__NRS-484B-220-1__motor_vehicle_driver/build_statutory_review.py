"""Map the three exact frozen one-way topics to both unselected direction cases."""
import hashlib
import json
from pathlib import Path

CASE=Path(__file__).resolve().parent
ROOT=CASE.parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    assignment_path=ROOT/'inputs'/CASE.name/'assignment.json'
    source_path=ROOT/'inputs/coverage/branch-sources.json'
    plan_path=CASE/'case-plan.json'
    construction_path=CASE/'native/drafts/manifest.json'
    saved_proof_path=CASE/'native/saved-proof.json'
    assignment=json.loads(assignment_path.read_text())
    source=json.loads(source_path.read_text())['laws']['NRS-484B-220-1']
    plan=json.loads(plan_path.read_text())
    topics=source['topics']
    cases={item['case_id']:item for item in plan['cases']}
    saved_proof=json.loads(saved_proof_path.read_text())
    saved={item['case']:item['measurement'] for item in saved_proof['positives']}
    if (source['original_assignment_id']!=CASE.name or
            source['law']['text']!=assignment['law_record']['text'] or
            set(topics)!={'text-0','reviewed-scope-0','reviewed-scope-1'} or
            {row['requirement'] for row in plan['requirement_dispositions']}!=set(topics) or
            set(cases)!={CASE.name+'__designated',CASE.name+'__opposite'} or
            set(saved)!={'designated','opposite'}):
        raise ValueError('Frozen one-way statutory scope differs')
    entries=[]
    for topic_id,topic in topics.items():
        for case_id,item in cases.items():
            measurement=saved[item['requested_setting']]
            entries.append({'topic_id':topic_id,'topic_kind':topic['kind'],
                            'topic_text':topic['text'],'case_id':case_id,
                            'requested_direction':item['requested_setting'],
                            'requested_sign_type':'R6-1',
                            'saved_actor_sha256':measurement['source_hashes']['native-observed.jsonl'],
                            'synthetic_signed_displacement_m':measurement['signed_ego_displacement_m'],
                            'synthetic_direction_matches_designation':measurement['direction_matches_designation'],
                            'synthetic_visible_sign_frames':measurement['visible_sign_frame_counts'],
                            'required_original_evidence':[
                                'source-hashed authoritative one-way highway designation',
                                'Native road-lane direction readback',
                                'physical one-way sign identity, direction and frame visibility',
                                'saved ego body occupation, heading and signed movement',
                                'independent source and statutory review'],
                            'status':'pending_original_authority_and_judgment',
                            'designation_authority_verified':False,
                            'physical_sign_verified':False,'legal_verdict':None})
    review={'format':'c150916-statutory-review-v1','assignment_id':CASE.name,
            'assignment_sha256':sha(assignment_path),'branch_source_sha256':sha(source_path),
            'case_plan_sha256':sha(plan_path),'construction_manifest_sha256':sha(construction_path),
            'saved_proof_sha256':sha(saved_proof_path),
            'topic_count':3,'candidate_topic_rows':entries,
            'original_native_observed':False,'legal_coverage_ready':False,'delivery_ready':False}
    (CASE/'statutory-review.json').write_text(json.dumps(review,indent=2)+'\n')
    return review


if __name__=='__main__':print(json.dumps({'rows':len(build()['candidate_topic_rows'])}))
