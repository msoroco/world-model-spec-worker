"""Independently audit C135709 exact statutory topics and synthetic limits."""
import hashlib
import json
from pathlib import Path

CASE=Path(__file__).resolve().parents[1]
ROOT=CASE.parents[1]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def audit():
    path=CASE/'statutory-review.json';review=json.loads(path.read_text())
    assignment=ROOT/'inputs'/CASE.name/'assignment.json'
    plan=CASE/'case-plan.json'
    source=json.loads(assignment.read_text());cases=json.loads(plan.read_text())
    if (review['format']!='c135709-statutory-review-v1' or
        review['assignment_id']!=CASE.name or
        review['assignment_sha256']!=sha(assignment) or
        review['case_plan_sha256']!=sha(plan) or
        review['law_id']!='NRS-484B-517' or
        review['exact_law_text']!=source['law_record']['text'] or
        review['selected_scope']!=cases['scope_branches'][0] or
        review['exception_adjudicated'] is not False or
        review['legal_verdict'] is not None or review['delivery_ready']):
        raise ValueError('C135709 statutory source differs')
    expected={d['requirement']:set(d['case_ids'])
              for d in cases['requirement_dispositions']}
    topics={d['requirement']:set(d['case_ids'])
            for d in review['source_topics'] if d['status']=='pending_original_review'}
    if topics!=expected or len(review['source_topics'])!=len(expected):
        raise ValueError('C135709 statutory topic coverage differs')
    witnesses={}
    for row in review['synthetic_case_measurements']:
        witness=row['case_id'].removeprefix(CASE.name+'__')
        if witness not in ('reference','contrast') or witness in witnesses:
            raise ValueError('C135709 statutory case duplicate')
        witnesses[witness]=row
        bundle=CASE/'offline/bundles'/witness/'primary'
        hashes={name:sha(bundle/'saved'/name) for name in
            ('native-observed.jsonl','camera-frames.jsonl','stand-review.jsonl','stand-readback.json')}
        if (row['saved_source_hashes']!=hashes or
            row['source_kind']!='synthetic_cpu' or row['legal_verdict'] is not None):
            raise ValueError('C135709 statutory saved source differs')
    if (set(witnesses)!={'reference','contrast'} or
        witnesses['reference']['full_body_stand_occupied_frames']!=0 or
        witnesses['contrast']['full_body_stand_occupied_frames']<=0):
        raise ValueError('C135709 statutory synthetic contrast differs')
    receipt={'format':'c135709-independent-statutory-audit-v1',
        'review_sha256':sha(path),'topics_checked':len(expected),
        'synthetic_cases_checked':len(witnesses),
        'original_native_observed':False,'delivery_ready':False}
    (CASE/'statutory-audit.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

if __name__=='__main__':print(json.dumps(audit()))
