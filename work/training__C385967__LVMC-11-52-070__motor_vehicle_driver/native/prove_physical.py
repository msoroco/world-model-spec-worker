"""Three source-backed synthetic physical preparation outcomes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from physical_preparation import assess
from prove_saved_sources import FOLDER, SCRATCH, source


def proof(suffix, kind):
    yaw=45 if suffix=='a' else 225
    case=FOLDER.name+'__probe_'+suffix
    config={'case_id':case,'requested_front_yaw_deg':yaw}
    if kind=='complete_motion':
        attempt=source(case,yaw)
    elif kind=='incomplete_motion':
        attempt=source(case,yaw,moving=True)
    elif kind=='missing_evidence':
        attempt=SCRATCH/f'probe_{suffix}-missing-physical'
        attempt.mkdir(exist_ok=True)
        for name in ('native_samples.jsonl','video_frames.jsonl'):
            (attempt/name).write_bytes((source(case,yaw)/name).read_bytes())
    else:
        raise ValueError('Unknown physical proof kind')
    if kind=='missing_evidence':
        status='unverified'
        sources={name:__import__('hashlib').sha256((attempt/name).read_bytes()).hexdigest()
                 for name in ('native_samples.jsonl','video_frames.jsonl')}
        observed={}
    else:
        observation=assess(attempt,config,allow_fixture=True)
        status=observation['status']
        sources=observation['source_hashes']
        observed={'maximum_speed_mps':observation['maximum_speed_mps'],
                  'body_frames_outside_authored_bay':observation['body_frames_outside_authored_bay']}
    return {'format':'c385967-physical-proof-v1','case_id':case,
        'physical_checks':{'maneuver':{'status':status,
            'method':'source-joined full-window parked body containment and at-rest diagnostic',
            'sources':sources,'details':observed}},
        'maneuver_completed':status=='met',
        'realized_observables':observed,
        'provenance_kind':'synthetic_fixture','diagnostic_fixture':True,
        'city_permission_verified':False,'legal_verdict':None}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--condition',choices=('a','b'),required=True)
    p.add_argument('--kind',choices=('complete_motion','incomplete_motion','missing_evidence'),required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    value=proof(a.condition,a.kind)
    a.output.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'case_id':value['case_id'],'kind':a.kind,
                      'status':value['physical_checks']['maneuver']['status']},sort_keys=True))
