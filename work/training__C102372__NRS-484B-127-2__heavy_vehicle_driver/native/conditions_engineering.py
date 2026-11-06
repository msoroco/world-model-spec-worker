"""Native requests for the controlled steady/lead-braking conditions pair."""
from __future__ import annotations
import hashlib
import json

ASSIGNMENT='training__C102372__NRS-484B-127-2__heavy_vehicle_driver'
CASES=('conditions_steady','conditions_lead_brake')
CANDIDATES=('primary','fallback1','fallback2','fallback3')
BASE={'ego_speed_mps':8.,'lead_speed_mps':8.,'initial_horizontal_gap_m':155.,
      'gap_gain':.25,'ego_brake_start_s':9.,'ego_brake_stop_s':13.,
      'lead_brake_start_s':8.,'lead_brake_stop_s':10.,
      'obstacle_x_m':285.,'rate_hz':20,'duration_s':24}
CHANGES={
    'conditions_steady':{
        'primary':{},'fallback1':{'initial_horizontal_gap_m':160.},
        'fallback2':{'ego_speed_mps':7.5},'fallback3':{'gap_gain':.5}},
    'conditions_lead_brake':{
        'primary':{},'fallback1':{'initial_horizontal_gap_m':160.},
        'fallback2':{'ego_brake_stop_s':12.},'fallback3':{'obstacle_x_m':295.}},
}
TRIGGERS={
    'conditions_steady':{
        'fallback1':{'metric':'minimum_surface_gap_m','op':'<','threshold':160.,
                     'source':'480 source-hashed Native truck bodies and hill-crest road surface'},
        'fallback2':{'metric':'surface_gap_compression_m','op':'>','threshold':1.,
                     'source':'480 source-hashed Native body/road-arc gap samples'},
        'fallback3':{'metric':'maximum_speed_difference_mps','op':'>','threshold':1.,
                     'source':'480 source-hashed Native ego/lead velocity readbacks'}},
    'conditions_lead_brake':{
        'fallback1':{'metric':'minimum_surface_gap_m','op':'<','threshold':142.,
                     'source':'480 source-hashed Native truck bodies and hill-crest road surface'},
        'fallback2':{'metric':'surface_gap_compression_m','op':'>','threshold':15.,
                     'source':'480 source-hashed Native body/road-arc gap samples'},
        'fallback3':{'metric':'minimum_lead_obstacle_clearance_m','op':'<','threshold':20.,
                     'source':'480 source-hashed Native lead and stopped-obstacle body footprints'}},
}


def construction(case,candidate):
    if case not in CASES or candidate not in CANDIDATES:
        raise ValueError('Unknown conditions case/candidate')
    return {'case':case,'case_id':ASSIGNMENT+'__'+case,'candidate':candidate,
            'law_id':'NRS-484B-127-2','cell_id':'C102372','actor':'heavy_vehicle_driver',
            'comparison_variable':'lead_braking_gap_compression_observed',
            'knobs':BASE|CHANGES[case][candidate],
            'fallback_trigger':TRIGGERS[case].get(candidate),
            'status':'planned_native_construction',
            'physical_conditions_permit_verified':False,'legal_verdict_claimed':False}


def request(case,candidate,frame):
    if not isinstance(frame,int) or not 0<=frame<480:
        raise ValueError('Full conditions frame index required')
    k=construction(case,candidate)['knobs'];t=frame/20
    if case=='conditions_steady':
        return {'time_s':t,'ego_speed_mps':k['ego_speed_mps'],
                'lead_speed_mps':k['lead_speed_mps'],
                'stopped_obstacle_requested':False}
    def braking(speed,start,stop):
        if t<=start:return speed
        if t>=stop:return 0.
        return round(speed*(stop-t)/(stop-start),6)
    return {'time_s':t,
            'ego_speed_mps':braking(k['ego_speed_mps'],k['ego_brake_start_s'],
                                   k['ego_brake_stop_s']),
            'lead_speed_mps':braking(k['lead_speed_mps'],k['lead_brake_start_s'],
                                    k['lead_brake_stop_s']),
            'stopped_obstacle_requested':True}


def check():
    for case in CASES:
        variants={candidate:construction(case,candidate) for candidate in CANDIDATES}
        fixed=('case','case_id','law_id','cell_id','actor','comparison_variable')
        if any(any(v[key]!=variants['primary'][key] for key in fixed)
               for v in variants.values()):
            raise ValueError('Conditions statutory identity changed')
        if len({hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()
                for v in variants.values()})!=4 or \
           len({TRIGGERS[case][n]['metric'] for n in CANDIDATES[1:]})!=3:
            raise ValueError('Conditions candidates/triggers repeat')
        for candidate,v in variants.items():
            k=v['knobs']
            if not (k['rate_hz']==20 and k['duration_s']==24 and
                    k['initial_horizontal_gap_m']>=155 and
                    0<k['ego_speed_mps']<=8 and 0<k['lead_speed_mps']<=8 and
                    0<k['gap_gain']<=.5 and
                    8<=k['lead_brake_start_s']<k['lead_brake_stop_s']<=10 and
                    9<=k['ego_brake_start_s']<k['ego_brake_stop_s']<=13 and
                    285<=k['obstacle_x_m']<=295):
                raise ValueError('Conditions request leaves controlled bounds')
            if request(case,candidate,0)['stopped_obstacle_requested']!=(
                    case=='conditions_lead_brake'):
                raise ValueError('Conditions event request differs')
    return {'passed':True,'case_count':2,'candidate_count':8,
            'fallback_metric_count':6,'original_capture_claimed':False}
