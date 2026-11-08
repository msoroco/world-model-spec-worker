"""Map exact frozen passing topics to three unselected synthetic probes."""
import hashlib
import json
from pathlib import Path

CASE=Path(__file__).resolve().parent;ROOT=CASE.parents[1];AID=CASE.name


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    assignment_path=ROOT/'inputs'/AID/'assignment.json'
    source_path=ROOT/'inputs/coverage/branch-sources.json'
    plan_path=CASE/'case-plan.json'
    proof_path=CASE/'native/pass-proof.json'
    response_path=CASE/'native/response-proof.json'
    assignment=json.loads(assignment_path.read_text())
    source=json.loads(source_path.read_text())['laws']['NRS-484B-213-1']
    plan=json.loads(plan_path.read_text())
    proof=json.loads(proof_path.read_text())
    responses=json.loads(response_path.read_text())
    response_by_distance={item['distance_m']:item['measurement'] for item in responses['fixtures']
                          if item['variant']=='constant_speed'}
    topics=source['topics']
    if (source['original_assignment_id']!=AID or source['law']['text']!=assignment['law_record']['text'] or
            set(topics)!={'text-0','reviewed-scope-0'} or
            {row['requirement'] for row in plan['requirement_dispositions']}!=set(topics) or
            len(proof['positives'])!=3):
        raise ValueError('Frozen left-of-center statutory scope differs')
    if set(response_by_distance)!={70,120,170}:
        raise ValueError('Saved vehicle response coverage differs')
    entries=[]
    for topic_id,topic in topics.items():
        for positive in proof['positives']:
            metric=positive['measurement']
            response=response_by_distance[positive['requested_clear_oncoming_distance_m']]
            if response['source_hashes']!=metric['source_hashes']:
                raise ValueError('Saved passing and response sources differ')
            entries.append({'topic_id':topic_id,'topic_kind':topic['kind'],'topic_text':topic['text'],
                            'requested_clear_distance_m':positive['requested_clear_oncoming_distance_m'],
                            'synthetic_entry_gap_m':metric['entry_oncoming_body_gap_m'],
                            'synthetic_first_nonpositive_gap_frame':metric['first_nonpositive_pre_return_oncoming_gap_frame'],
                            'synthetic_return_frame':metric['first_return_after_pass_frame'],
                            'saved_actor_sha256':metric['source_hashes']['native-observed.jsonl'],
                            'synthetic_oncoming_speed_drop_mps':response['response']['oncoming']['maximum_left_phase_speed_drop_mps'],
                            'synthetic_overtaken_speed_drop_mps':response['response']['overtaken']['maximum_left_phase_speed_drop_mps'],
                            'required_original_evidence':['Native two-lane two-direction highway readback',
                                'observed full-body left-of-center pass and return',
                                'driver-eye hill-crest sightline throughout pass',
                                'source-bound approaching and overtaken vehicle response',
                                'independent sufficient-distance and noninterference review'],
                            'status':'pending_original_and_judgment','legal_verdict':None})
    review={'format':'c102951-statutory-review-v1','assignment_id':AID,
            'assignment_sha256':sha(assignment_path),'branch_source_sha256':sha(source_path),
            'case_plan_sha256':sha(plan_path),'pass_proof_sha256':sha(proof_path),
            'response_proof_sha256':sha(response_path),
            'topic_count':2,'candidate_topic_rows':entries,
            'original_native_observed':False,'legal_coverage_ready':False,'delivery_ready':False}
    (CASE/'statutory-review.json').write_text(json.dumps(review,indent=2)+'\n')
    return review

if __name__=='__main__':print(json.dumps({'rows':len(build()['candidate_topic_rows'])}))
