"""Owned-endpoint trajectory requests for the planned one-lane passing case.

The saved passing measurement, rather than this request, decides whether a
capture contains a complete overtake and return. No physical clearance is
inferred from the requested trajectory.
"""
from __future__ import annotations
import hashlib
import json

CASE='passing_overtake'
ASSIGNMENT='training__C102372__NRS-484B-127-2__heavy_vehicle_driver'
CANDIDATES=('primary','fallback1','fallback2','fallback3')
BASE={'ego_speed_mps':12.,'lead_speed_mps':8.,'opposing_center_y_m':2.,
      'enter_start_s':2.,'enter_end_s':4.,'return_start_s':16.,
      'return_end_s':18.,'rate_hz':20,'duration_s':24}
CHANGES={
    'primary':{},
    'fallback1':{'ego_speed_mps':12.5},
    'fallback2':{'opposing_center_y_m':2.3},
    'fallback3':{'enter_start_s':1.5,'enter_end_s':3.5,
                 'return_start_s':17.,'return_end_s':19.},
}
TRIGGERS={
    'fallback1':{'metric':'final_center_offset_m','op':'<','threshold':50.,
                 'source':'480 source-hashed original Native truck body centers and frame times'},
    'fallback2':{'metric':'minimum_body_clearance_m','op':'<','threshold':1.5,
                 'source':'480 source-hashed original Native 80-inch truck body footprints'},
    'fallback3':{'metric':'opposing_lane_frames','op':'<','threshold':300,
                 'source':'480 source-hashed original Native lane/body frame joins'},
}


def construction(candidate):
    if candidate not in CANDIDATES:raise ValueError('Unknown passing candidate')
    return {'case':CASE,'case_id':ASSIGNMENT+'__'+CASE,'candidate':candidate,
            'law_id':'NRS-484B-127-2','cell_id':'C102372',
            'actor':'heavy_vehicle_driver','comparison_variable':'passing_sequence_observed',
            'knobs':BASE|CHANGES[candidate],
            'fallback_trigger':TRIGGERS.get(candidate),
            'status':'planned_native_construction',
            'physical_opposing_clearance_verified':False,
            'legal_verdict_claimed':False}


def request(candidate,frame):
    """Return 20 Hz speed/lateral requests; a saved original trace must verify them."""
    if not isinstance(frame,int) or not 0<=frame<480:
        raise ValueError('Full passing frame index required')
    k=construction(candidate)['knobs'];t=frame/k['rate_hz'];y0=-2.;y1=k['opposing_center_y_m']
    if t<k['enter_start_s']:y=y0
    elif t<k['enter_end_s']:
        y=y0+(y1-y0)*(t-k['enter_start_s'])/(k['enter_end_s']-k['enter_start_s'])
    elif t<k['return_start_s']:y=y1
    elif t<k['return_end_s']:
        y=y1+(y0-y1)*(t-k['return_start_s'])/(k['return_end_s']-k['return_start_s'])
    else:y=y0
    return {'time_s':t,'ego_speed_mps':k['ego_speed_mps'],
            'lead_speed_mps':k['lead_speed_mps'],'ego_target_y_m':round(y,6),
            'intended_lane_id':1 if y>=0 else -1}


def check():
    variants={name:construction(name) for name in CANDIDATES}
    fixed=('case','case_id','law_id','cell_id','actor','comparison_variable')
    if any(any(v[key]!=variants['primary'][key] for key in fixed)
           for v in variants.values()):raise ValueError('Passing statutory identity changed')
    if len({hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()
            for v in variants.values()})!=4:
        raise ValueError('Passing candidates are not distinct')
    if len({TRIGGERS[n]['metric'] for n in CANDIDATES[1:]})!=3:
        raise ValueError('Passing fallback triggers repeat')
    for name in CANDIDATES:
        k=variants[name]['knobs']
        if not (k['rate_hz']==20 and k['duration_s']==24 and
                0<k['enter_start_s']<k['enter_end_s']<
                k['return_start_s']<k['return_end_s']<24 and
                1.3<k['opposing_center_y_m']<2.7 and
                0<k['lead_speed_mps']<k['ego_speed_mps']):
            raise ValueError('Passing trajectory timing or lane differs')
        if request(name,0)['intended_lane_id']!=-1 or \
           request(name,479)['intended_lane_id']!=-1 or \
           request(name,200)['intended_lane_id']!=1:
            raise ValueError('Passing trajectory does not depart and return')
    return {'passed':True,'case_id':ASSIGNMENT+'__'+CASE,
            'candidate_count':4,'fallback_metric_count':3,
            'original_capture_claimed':False}
