"""Independently audit the C10052 exact source-topic branch mapping."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
LAW='NRS-484B-270-3'
ASSIGNMENT='training__C10052__NRS-484B-270-3__motor_vehicle_driver'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    source=json.loads((ROOT/'inputs/coverage/branch-sources.json').read_text())['laws'][LAW]
    matrix_path=ROOT/'work/_shared/branch-coverage.json'
    matrix=json.loads(matrix_path.read_text())['laws'][LAW]
    local=json.loads((ROOT/'work'/ASSIGNMENT/'statutory-branch-review.json').read_text())
    branches=matrix['branches']
    assert len(branches)==len(local['branches'])==12
    assert matrix['source_topic_count']==len(source['topics'])==9
    assert {b['branch_id'].split('__')[-1] for b in branches}=={b['id'] for b in local['branches']}
    assert all(b['assignment_id']==ASSIGNMENT and b['status']=='pending_review'
               for b in branches)
    mapping={b['branch_id'].split('__')[-1]:set(b['topic_ids']) for b in branches}
    assert mapping['prohibition_stop_stand']=={'text-1','reviewed-scope-0'}
    assert all(mapping[name]=={'text-1'} for name in
               ('prohibition_enter','prohibition_park','prohibition_drive'))
    assert mapping['yield_riders']==mapping['yield_qualifying_pedestrian']=={'text-0'}
    for i,letter in enumerate('abcdef',2):
        assert mapping['exception_'+letter]=={'text-'+str(i)}
    assert set().union(*mapping.values())==set(source['topics'])
    shared=json.loads((ROOT/'work/_shared/branch-review.json').read_text())
    assert shared['coverage_sha256']==sha(matrix_path)
    assert LAW in shared['missing_branches']
    return {'passed':True,'law_id':LAW,'topics':9,'pending_branches':12,
            'runnable_branches':0,'coverage_sha256':sha(matrix_path)}


if __name__=='__main__':
    print(json.dumps(audit(),indent=2))
