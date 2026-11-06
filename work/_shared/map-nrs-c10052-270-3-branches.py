"""Map exact NRS 484B.270(3) source topics to reviewed pending branches."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HERE=ROOT/'work/_shared'
ASSIGNMENT='training__C10052__NRS-484B-270-3__motor_vehicle_driver'
LAW='NRS-484B-270-3'
TOPICS={
    'prohibition_enter':['text-1'],
    'prohibition_stop_stand':['text-1','reviewed-scope-0'],
    'prohibition_park':['text-1'],
    'prohibition_drive':['text-1'],
    'yield_riders':['text-0'],
    'yield_qualifying_pedestrian':['text-0'],
    'exception_a':['text-2'],
    'exception_b':['text-3'],
    'exception_c':['text-4'],
    'exception_d':['text-5'],
    'exception_e':['text-6'],
    'exception_f':['text-7']}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n')


def run():
    source=json.loads((ROOT/'inputs/coverage/branch-sources.json').read_text())['laws'][LAW]
    review=json.loads((ROOT/'work'/ASSIGNMENT/'statutory-branch-review.json').read_text())
    ids={row['id'] for row in review['branches']}
    if ids!=set(TOPICS):raise ValueError('Source branch mapping differs from reviewed clause')
    if set().union(*(set(value) for value in TOPICS.values()))!=set(source['topics']):
        raise ValueError('Unmapped NRS 484B.270(3) source topic')
    matrix_path=HERE/'branch-coverage.json';matrix=json.loads(matrix_path.read_text())
    matrix['laws'][LAW]={
        'review_status':'reviewed_source_topics_pending_delivery',
        'source_topic_count':len(source['topics']),
        'branches':[{'branch_id':'nrs_484b_270_3__'+row['id'],
                     'topic_ids':TOPICS[row['id']],
                     'status':'pending_review',
                     'assignment_id':ASSIGNMENT,
                     'note':row['exact_text']+'; '+row['status']}
                    for row in review['branches']]}
    write(matrix_path,matrix)
    review_path=HERE/'branch-review.json';shared=json.loads(review_path.read_text())
    shared['coverage_sha256']=sha(matrix_path)
    note='C10052 NRS 484B.270(3) now maps its nine exact source topics to twelve pending clause branches; no branch is runnable.'
    if note not in shared['review_method']:
        shared['review_method']+=' '+note
    write(review_path,shared)
    return {'law_id':LAW,'topics':len(source['topics']),'branches':len(TOPICS),
            'runnable':0,'coverage_sha256':sha(matrix_path)}


if __name__=='__main__':
    print(json.dumps(run(),indent=2))
