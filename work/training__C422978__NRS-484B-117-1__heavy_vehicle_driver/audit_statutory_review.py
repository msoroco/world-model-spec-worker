"""Independently audit frozen topic coverage against saved synthetic body rows."""
import hashlib
import json
from pathlib import Path

CASE = Path(__file__).resolve().parent
ROOT = CASE.parents[1]
AID = CASE.name
CASES = ('reference','contrast')
CANDIDATES = ('primary','fallback1','fallback2','fallback3')
TOPICS = ('text-0','text-1','text-2','text-3','text-4','text-5','reviewed-scope-0')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(path):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if len(rows) != 480:
        raise ValueError('Statutory audit saved row count differs')
    overlap, inside, lane = [], [], 0
    for index, row in enumerate(rows):
        if row['frame'] != index or row['source_kind'] != 'synthetic_cpu' or row['vehicle_blueprint'] != 'vehicle.carlamotors.carlacola':
            raise ValueError('Statutory audit saved actor identity differs')
        x = [p[0] for p in row['body_native_xy_m']]
        y = [p[1] for p in row['body_native_xy_m']]
        if row['speed_mps'] > .1:
            if max(x)>0 and min(x)<140 and max(y)>3.5 and min(y)<7.5:
                overlap.append(index)
            if min(x)>=0 and max(x)<=140 and min(y)>=3.5 and max(y)<=7.5:
                inside.append(index)
        if row.get('native_lane_id') == -2:
            lane += 1
    return {'moving_overlap_frames':len(overlap),
            'first_overlap_frame':overlap[0] if overlap else None,
            'full_body_inside_frames':len(inside),
            'native_lane_readback_frames':lane}


def audit():
    review_path = CASE/'statutory-review.json'
    review = json.loads(review_path.read_text())
    paths = {'assignment_sha256':ROOT/'inputs'/AID/'assignment.json',
             'branch_source_sha256':ROOT/'inputs/coverage/branch-sources.json',
             'case_plan_sha256':CASE/'case-plan.json',
             'saved_proof_sha256':CASE/'native/saved-proof.json'}
    paths['exception_proof_sha256'] = CASE/'native/exception-proof.json'
    if (review['format'] != 'c422978-heavy-statutory-review-v1' or
            review['assignment_id'] != AID or
            any(review[key] != sha(path) for key,path in paths.items()) or
            review['topic_count'] != 7 or len(review['candidate_topic_rows']) != 56 or
            any(review[key] for key in ('original_native_observed','legal_coverage_ready','delivery_ready'))):
        raise ValueError('Statutory review scope or source binding differs')
    assignment = json.loads(paths['assignment_sha256'].read_text())
    topics = json.loads(paths['branch_source_sha256'].read_text())['laws']['NRS-484B-117-1']['topics']
    dispositions = {row['requirement'] for row in json.loads(paths['case_plan_sha256'].read_text())['requirement_dispositions']}
    if (set(topics) != set(TOPICS) or dispositions != set(TOPICS) or
            assignment['law_record']['text'] != json.loads(paths['branch_source_sha256'].read_text())['laws']['NRS-484B-117-1']['law']['text']):
        raise ValueError('Frozen statutory topic set differs')
    expected = {(topic,case,candidate) for topic in TOPICS for case in CASES for candidate in CANDIDATES}
    seen, source_rows = set(), 0
    cached = {}
    exception_index = {(row['case'],row['candidate']):row['measurement']
                       for row in json.loads(paths['exception_proof_sha256'].read_text())['positives']}
    for row in review['candidate_topic_rows']:
        key = (row['topic_id'],row['case'],row['candidate'])
        if key not in expected or key in seen:
            raise ValueError('Statutory candidate topic identity differs')
        seen.add(key)
        topic = topics[row['topic_id']]
        if (row['topic_text'] != topic['text'] or row['topic_kind'] != topic['kind'] or
                row['status'] != 'pending_original_and_context' or row['legal_verdict'] is not None or
                not row['required_original_evidence']):
            raise ValueError('Statutory topic evidence or status differs')
        pair = (row['case'],row['candidate'])
        if pair not in cached:
            path = CASE/'native/saved-fixtures'/pair[0]/pair[1]/'native-observed.jsonl'
            cached[pair] = (sha(path),metrics(path))
            source_rows += 480
        if (row['saved_actor_sha256'],row['synthetic_measurement']) != cached[pair]:
            raise ValueError('Statutory measurement differs from saved actor rows')
        exception = exception_index[pair]
        if (row['synthetic_reported_exception_pattern'] != exception['reported_exception_pattern'] or
                row['exception_packet_sha256'] != sha(CASE/'native/saved-fixtures'/pair[0]/pair[1]/'exception-evidence.json') or
                exception['exception_applies'] is not None or exception['legal_verdict'] is not None):
            raise ValueError('Statutory exception packet differs')
    if seen != expected or source_rows != 3840:
        raise ValueError('Statutory topic cross product incomplete')
    result = {'format':'c422978-heavy-independent-statutory-audit-v1',
              'review_sha256':sha(review_path), 'topics':len(TOPICS),
              'candidate_topic_rows':len(seen),'saved_rows_recomputed':source_rows,
              'legal_coverage_ready':False,'delivery_ready':False}
    (CASE/'statutory-review-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__ == '__main__':
    result = audit()
    print(json.dumps({'topics':result['topics'],'rows':result['candidate_topic_rows'],
                      'saved_rows':result['saved_rows_recomputed']}))
