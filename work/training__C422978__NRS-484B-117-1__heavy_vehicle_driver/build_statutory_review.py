"""Map every frozen sidewalk statute topic to measured CPU evidence and pending proof."""
import hashlib
import json
from pathlib import Path

CASE = Path(__file__).resolve().parent
ROOT = CASE.parents[1]
AID = CASE.name
TOPICS = {
    'text-0': ['original Native driving and full body footprint',
               'source-authorized City sidewalk boundary',
               'per-frame permanent or temporary driveway/alley entrance width'],
    'text-1': ['legal review of violation classification after physical and exception evidence'],
    'text-2': ['original powertrain authority proving solely electric',
               'original wheel-design authority proving three wheels',
               'operator exception role evidence'],
    'text-3': ['authorized emergency vehicle status and operation at the event'],
    'text-4': ['law-enforcement agency and authorized employee status',
               'source evidence of official duties at the event'],
    'text-5': ['security-guard status under cited definition',
               'source evidence of official duties at the event'],
    'reviewed-scope-0': ['original Native and City sidewalk proof',
                         'driveway/alley crossing review',
                         'three-wheel electric exception and operator-role review'],
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    assignment_path = ROOT/'inputs'/AID/'assignment.json'
    source_path = ROOT/'inputs/coverage/branch-sources.json'
    plan_path = CASE/'case-plan.json'
    proof_path = CASE/'native/saved-proof.json'
    assignment = json.loads(assignment_path.read_text())
    source = json.loads(source_path.read_text())['laws']['NRS-484B-117-1']
    plan = json.loads(plan_path.read_text())
    saved = json.loads(proof_path.read_text())
    topics = source['topics']
    if (source['original_assignment_id'] != AID or
            source['law']['text'] != assignment['law_record']['text'] or
            set(topics) != set(TOPICS) or
            {d['requirement'] for d in plan['requirement_dispositions']} != set(TOPICS) or
            len(saved['positives']) != 8):
        raise ValueError('Frozen sidewalk statutory scope differs')
    entries = []
    for topic_id, topic in topics.items():
        for positive in saved['positives']:
            metric = positive['measurement']
            if metric['source_kind'] != 'synthetic_cpu' or metric['legal_verdict'] is not None:
                raise ValueError('Saved proof cannot support statutory review')
            entries.append({'topic_id':topic_id, 'topic_kind':topic['kind'],
                            'topic_text':topic['text'], 'case':positive['case'],
                            'candidate':positive['candidate'],
                            'synthetic_measurement':{
                                'moving_overlap_frames':metric['moving_sidewalk_overlap_frames'],
                                'first_overlap_frame':metric['first_moving_sidewalk_overlap_frame'],
                                'full_body_inside_frames':metric['full_body_inside_sidewalk_frames'],
                                'native_lane_readback_frames':metric['native_sidewalk_lane_readback_frames']},
                            'saved_actor_sha256':metric['source_hashes']['native-observed.jsonl'],
                            'required_original_evidence':TOPICS[topic_id],
                            'status':'pending_original_and_context',
                            'legal_verdict':None})
    review = {'format':'c422978-heavy-statutory-review-v1',
              'assignment_id':AID, 'assignment_sha256':sha(assignment_path),
              'branch_source_sha256':sha(source_path), 'case_plan_sha256':sha(plan_path),
              'saved_proof_sha256':sha(proof_path), 'topic_count':len(topics),
              'candidate_topic_rows':entries,
              'original_native_observed':False,'legal_coverage_ready':False,
              'delivery_ready':False}
    (CASE/'statutory-review.json').write_text(json.dumps(review,indent=2)+'\n')
    return review


if __name__ == '__main__':
    print(json.dumps({'rows':len(build()['candidate_topic_rows'])}))
