"""Independent frozen-topic and saved-source audit for C102951 passing review."""
import hashlib
import json
from pathlib import Path

CASE=Path(__file__).resolve().parent;ROOT=CASE.parents[1];AID=CASE.name


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    path=CASE/'statutory-review.json';review=json.loads(path.read_text())
    sources={'assignment_sha256':ROOT/'inputs'/AID/'assignment.json',
             'branch_source_sha256':ROOT/'inputs/coverage/branch-sources.json',
             'case_plan_sha256':CASE/'case-plan.json',
             'pass_proof_sha256':CASE/'native/pass-proof.json'}
    if review['format']!='c102951-statutory-review-v1' or review['assignment_id']!=AID or any(review[k]!=sha(v) for k,v in sources.items()) or review['topic_count']!=2 or len(review['candidate_topic_rows'])!=6 or any(review[k] for k in ('original_native_observed','legal_coverage_ready','delivery_ready')):
        raise ValueError('Passing statutory review identity differs')
    topics=json.loads(sources['branch_source_sha256'].read_text())['laws']['NRS-484B-213-1']['topics']
    if set(topics)!={'text-0','reviewed-scope-0'}:raise ValueError('Passing topic set differs')
    expected={(topic,distance) for topic in topics for distance in (70,120,170)}
    seen=set();rows_checked=0;cache={}
    for row in review['candidate_topic_rows']:
        key=(row['topic_id'],row['requested_clear_distance_m'])
        if key not in expected or key in seen:raise ValueError('Passing statutory topic row differs')
        seen.add(key)
        topic=topics[row['topic_id']]
        if row['topic_text']!=topic['text'] or row['topic_kind']!=topic['kind'] or row['status']!='pending_original_and_judgment' or row['legal_verdict'] is not None or len(row['required_original_evidence'])!=5:
            raise ValueError('Passing statutory topic status differs')
        d=key[1]
        if d not in cache:
            actor=CASE/'native/saved-fixtures'/str(d)/'native-observed.jsonl'
            rows=[json.loads(line) for line in actor.read_text().splitlines()]
            if len(rows)!=480:raise ValueError('Passing saved row count differs')
            entry=next(i for i,r in enumerate(rows) if r['ego_y_m']+.9>0)
            passed=False;returned=None;nonpositive=None
            for i,r in enumerate(rows):
                if i>=entry and r['ego_x_m']-2.2>r['overtaken_x_m']+2.2:passed=True
                if i>=entry and returned is None and round(r['oncoming_x_m']-r['ego_x_m']-4.4,3)<=0:nonpositive=i if nonpositive is None else nonpositive
                if passed and r['ego_y_m']+.9<=0:returned=i;break
            cache[d]=(sha(actor),round(rows[entry]['oncoming_x_m']-rows[entry]['ego_x_m']-4.4,3),nonpositive,returned)
            rows_checked+=480
        if (row['saved_actor_sha256'],row['synthetic_entry_gap_m'],row['synthetic_first_nonpositive_gap_frame'],row['synthetic_return_frame'])!=cache[d]:
            raise ValueError('Passing statutory saved metric differs')
    if seen!=expected or rows_checked!=1440:raise ValueError('Passing statutory coverage incomplete')
    result={'format':'c102951-independent-statutory-audit-v1','topics':2,'rows':6,
            'saved_rows_checked':rows_checked,'review_sha256':sha(path),
            'legal_coverage_ready':False,'delivery_ready':False}
    (CASE/'statutory-review-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(audit()))
