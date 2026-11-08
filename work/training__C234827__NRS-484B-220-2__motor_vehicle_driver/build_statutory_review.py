"""Map exact rotary-island topics to authored cases without a legal verdict."""
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
    manifest_path=CASE/'native/drafts/manifest.json'
    assignment=json.loads(assignment_path.read_text())
    source=json.loads(source_path.read_text())['laws']['NRS-484B-220-2']
    plan=json.loads(plan_path.read_text())
    if (source['original_assignment_id']!=CASE.name or
            source['law']['text']!=assignment['law_record']['text'] or
            set(source['topics'])!={'text-0','reviewed-scope-0'} or
            {row['requirement'] for row in plan['requirement_dispositions']}!=set(source['topics']) or
            {row['case_id'] for row in plan['cases']}!=
            {CASE.name+'__reference',CASE.name+'__contrast'}):
        raise ValueError('Rotary statutory source scope differs')
    entries=[]
    for topic_id,topic in source['topics'].items():
        for case in ('reference','contrast'):
            entries.append({'topic_id':topic_id,'topic_kind':topic['kind'],
                'topic_text':topic['text'],'case_id':CASE.name+'__'+case,
                'requested_island_side':'left' if case=='reference' else 'right',
                'required_original_evidence':[
                    'Native physical rotary island and continuous body-clearance readback',
                    'synchronized original ego pose, speed and footprint',
                    'frame-reviewed island and traffic-control visibility',
                    'source-hashed accepted-recording equivalence review or new original evidence',
                    'independent statutory and comparison audit'],
                'existing_membership_only':True,
                'status':'pending_original_island_and_judgment',
                'physical_island_verified':False,'legal_verdict':None})
    review={'format':'c234827-statutory-review-v1',
        'assignment_id':CASE.name,
        'assignment_sha256':sha(assignment_path),
        'branch_source_sha256':sha(source_path),
        'case_plan_sha256':sha(plan_path),
        'construction_manifest_sha256':sha(manifest_path),
        'topic_count':2,'candidate_topic_rows':entries,
        'accepted_originals_replayed':0,
        'original_native_observed':False,
        'legal_coverage_ready':False,'delivery_ready':False}
    (CASE/'statutory-review.json').write_text(json.dumps(review,indent=2)+'\n')
    return review


if __name__=='__main__':print(json.dumps({'rows':len(build()['candidate_topic_rows'])}))
