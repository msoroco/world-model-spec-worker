"""Law-preserving Native requests for the controlled no-passing case."""
from __future__ import annotations
import hashlib
import json

CASE='passing_hold'
ASSIGNMENT='training__C102372__NRS-484B-127-2__heavy_vehicle_driver'
CANDIDATES=('primary','fallback1','fallback2','fallback3')
BASE={'ego_speed_mps':8.,'lead_speed_mps':8.,'target_gap_m':26.,
      'gap_gain':.25,'lane_center_gain':.5,'rate_hz':20,'duration_s':24}
CHANGES={'primary':{},'fallback1':{'ego_speed_mps':7.5},
         'fallback2':{'lead_speed_mps':8.5,'gap_gain':.4},
         'fallback3':{'lane_center_gain':1.}}
TRIGGERS={
    'fallback1':{'metric':'minimum_body_clearance_m','op':'<','threshold':20.,
                 'source':'source-hashed original Native truck body footprints over 480 frames'},
    'fallback2':{'metric':'maximum_speed_difference_mps','op':'>','threshold':1.,
                 'source':'source-hashed original Native ego and lead velocities over 480 frames'},
    'fallback3':{'metric':'maximum_lane_center_error_m','op':'>','threshold':.3,
                 'source':'source-hashed original Native ego body centers over 480 frames'},
}


def construction(candidate):
    if candidate not in CANDIDATES:raise ValueError('Unknown hold candidate')
    return {'case':CASE,'case_id':ASSIGNMENT+'__'+CASE,'candidate':candidate,
            'law_id':'NRS-484B-127-2','cell_id':'C102372',
            'actor':'heavy_vehicle_driver','comparison_variable':'passing_sequence_observed',
            'knobs':BASE|CHANGES[candidate],'fallback_trigger':TRIGGERS.get(candidate),
            'status':'planned_native_construction','legal_verdict_claimed':False}


def speed_requests(candidate,gap):
    k=construction(candidate)['knobs']
    ego=max(.5,min(k['ego_speed_mps']+2,
                   k['ego_speed_mps']+k['gap_gain']*(gap-k['target_gap_m'])))
    return ego,k['lead_speed_mps']


def check():
    variants={name:construction(name) for name in CANDIDATES}
    fixed=('case','case_id','law_id','cell_id','actor','comparison_variable')
    if any(any(v[key]!=variants['primary'][key] for key in fixed)
           for v in variants.values()):raise ValueError('Hold statutory identity changed')
    if len({hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()
            for v in variants.values()})!=4:
        raise ValueError('Hold candidates are not distinct')
    if len({TRIGGERS[n]['metric'] for n in CANDIDATES[1:]})!=3:
        raise ValueError('Hold fallback triggers repeat')
    for name in CANDIDATES:
        k=variants[name]['knobs']
        if not (k['rate_hz']==20 and k['duration_s']==24 and
                0<k['ego_speed_mps']<12 and 0<k['lead_speed_mps']<12 and
                k['target_gap_m']>=20 and 0<k['gap_gain']<1 and
                0<k['lane_center_gain']<=1):
            raise ValueError('Hold request leaves safe bounds')
        if speed_requests(name,26.)[0]<=0:
            raise ValueError('Hold request lacks positive velocity')
    return {'passed':True,'case_id':ASSIGNMENT+'__'+CASE,
            'candidate_count':4,'fallback_metric_count':3,
            'original_capture_claimed':False}
