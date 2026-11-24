"""Independent source-bound comparisons of the two exclusion controls."""
import hashlib
import json
from pathlib import Path

from audit_sources import HERE, audit

BASE = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def run():
    for suffix in ('device_controlled','opposing_no_turn','opposing_left_turn'):
        audit(suffix)
    baseline_root = BASE/'selected-v3/controlled_2/primary/sources'
    baseline = read(baseline_root/'actor-history.json')['rows']
    device_root = HERE/'device_controlled/sources'
    device = read(device_root/'actor-history.json')['rows']
    no_turn_root = HERE/'opposing_no_turn/sources'
    no_turn = read(no_turn_root/'actor-history.json')['rows']
    turn_root = HERE/'opposing_left_turn/sources'
    turn = read(turn_root/'actor-history.json')['rows']
    for left,right in zip(baseline,device):
        if (left['ego']!=right['ego'] or left['other']!=right['other'] or
                left['time_s']!=right['time_s']):
            raise ValueError('Device comparison changed actor trajectories')
    if sha(baseline_root/'road.xodr')==sha(device_root/'road.xodr'):
        raise ValueError('Device comparison lacks authored road difference')
    for left,right in zip(no_turn,turn):
        if left['ego']!=right['ego'] or left['time_s']!=right['time_s']:
            raise ValueError('Opposing turn comparison changed ego or clock')
        if left['time_s']<=6 and left['other']['center_xyz_m']!=right['other']['center_xyz_m']:
            raise ValueError('Opposing turn comparison changed approach')
    if sha(no_turn_root/'road.xodr')!=sha(turn_root/'road.xodr'):
        raise ValueError('Opposing turn comparison changed road')
    if no_turn[250]['other']['center_xyz_m']==turn[250]['other']['center_xyz_m']:
        raise ValueError('Opposing left-turn trajectory did not diverge')
    return {'format':'c111294-2502-exception-comparison-v1',
            'device':{'case_ids':[BASE.name+'__controlled_2',BASE.name+'__device_controlled'],
                      'fixed_actor_histories':True,
                      'changed_variable':'authored traffic-control signal; official governance unresolved',
                      'source_sha256':[sha(baseline_root/'actor-history.json'),
                                       sha(device_root/'actor-history.json')]},
            'opposing_turn':{'case_ids':[BASE.name+'__opposing_no_turn',
                                          BASE.name+'__opposing_left_turn'],
                              'fixed_ego_and_preentry_approach':True,
                              'changed_variable':'other driver left-turn request and postentry trajectory',
                              'source_sha256':[sha(no_turn_root/'actor-history.json'),
                                               sha(turn_root/'actor-history.json')]},
            'original_native_observed':False,'legal_verdict':None}


if __name__=='__main__':
    result=run()
    path=HERE/'comparison-audit.json'
    path.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'comparison_audit_sha256':sha(path),'comparisons':2},sort_keys=True))
