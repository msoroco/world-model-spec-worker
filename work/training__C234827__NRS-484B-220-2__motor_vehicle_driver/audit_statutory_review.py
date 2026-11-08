"""Independent exact-topic rotary statutory coverage audit."""
import hashlib
import json
from pathlib import Path

CASE=Path(__file__).resolve().parent
ROOT=CASE.parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    path=CASE/'statutory-review.json'
    review=json.loads(path.read_text())
    paths={'assignment_sha256':ROOT/'inputs'/CASE.name/'assignment.json',
           'branch_source_sha256':ROOT/'inputs/coverage/branch-sources.json',
           'case_plan_sha256':CASE/'case-plan.json',
           'construction_manifest_sha256':CASE/'native/drafts/manifest.json'}
    saved_path=CASE/'native/saved-proof.json'
    saved_proof=json.loads(saved_path.read_text())
    saved={item['case']:item['measurement'] for item in saved_proof['positives']}
    source=json.loads(paths['branch_source_sha256'].read_text())['laws']['NRS-484B-220-2']
    assignment=json.loads(paths['assignment_sha256'].read_text())
    if (review['format']!='c234827-statutory-review-v1' or
            review['assignment_id']!=CASE.name or
            any(review[key]!=sha(value) for key,value in paths.items()) or
            review['saved_proof_sha256']!=sha(saved_path) or
            source['law']['text']!=assignment['law_record']['text'] or
            review['topic_count']!=2 or len(review['candidate_topic_rows'])!=4 or
            review['accepted_originals_replayed']!=0 or
            review['original_native_observed'] or review['legal_coverage_ready'] or
            review['delivery_ready']):
        raise ValueError('Rotary statutory provenance differs')
    expected={(topic,case) for topic in ('text-0','reviewed-scope-0')
              for case in ('reference','contrast')}
    seen=set()
    for item in review['candidate_topic_rows']:
        case=item['case_id'].removeprefix(CASE.name+'__')
        topic=item['topic_id']
        if (topic,case) not in expected or (topic,case) in seen:
            raise ValueError('Rotary statutory topic/case coverage differs')
        seen.add((topic,case))
        frozen=source['topics'][topic]
        metric=saved[case]
        if (item['topic_kind']!=frozen['kind'] or
                item['topic_text']!=frozen['text'] or
                item['requested_island_side']!=('left' if case=='reference' else 'right') or
                item['saved_actor_sha256']!=metric['source_hashes']['native-observed.jsonl'] or
                item['synthetic_angular_progress_rad']!=metric['angular_progress_rad'] or
                item['synthetic_requested_side_continuous']!=metric['continuous_requested_side'] or
                item['synthetic_minimum_body_clearance_m']!=metric['minimum_body_island_clearance_m'] or
                item['status']!='pending_original_island_and_judgment' or
                not item['existing_membership_only'] or
                item['physical_island_verified'] or
                item['legal_verdict'] is not None or
                len(item['required_original_evidence'])!=5):
            raise ValueError('Rotary statutory row overclaims evidence')
    if seen!=expected:raise ValueError('Rotary statutory topic coverage incomplete')
    result={'format':'c234827-independent-statutory-audit-v1',
            'review_sha256':sha(path),'exact_topics_checked':2,
            'candidate_topic_rows_checked':4,
            'accepted_originals_replayed':0,
            'original_native_observed':False,'legal_coverage_ready':False,
            'delivery_ready':False}
    (CASE/'statutory-review-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':print(json.dumps(audit()))
