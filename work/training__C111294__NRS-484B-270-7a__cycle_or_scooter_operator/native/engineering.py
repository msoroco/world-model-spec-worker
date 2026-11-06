"""Unselected bicycle and motorist interaction candidates with source-bound triggers."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

CASES=('witness_1','witness_2')
CANDIDATES=('primary','fallback1','fallback2','fallback3')
BASE={'bicycle_route_tracking_lookahead_m':5.0,
      'motorist_clearance_buffer_s':1.0,'overview_fov_deg':90.0,
      'rate_hz':20,'duration_s':24.0,
      'camera_profile':['overview','bicycle_approach','motorist_approach','conflict']}
CHANGES={'primary':{},'fallback1':{'bicycle_route_tracking_lookahead_m':3.0},
         'fallback2':{'motorist_clearance_buffer_s':2.0},
         'fallback3':{'overview_fov_deg':105.0}}
TRIGGERS={
 'fallback1':{'metric':'max_bicycle_route_cross_track_error_m','op':'>','threshold':0.45,
              'source':'original Native bicycle pose joined to authored route and map readback'},
 'fallback2':{'metric':'min_motorist_conflict_clearance_s','op':'<','threshold':1.0,
              'source':'original Native motor-vehicle pose and full body joined to bicycle full body'},
 'fallback3':{'metric':'min_projected_body_frame_margin_px','op':'<','threshold':40,
              'source':'original Native bicycle/motor-vehicle full-body vertices, original overview camera pose/calibration, and decoded overview frame count'}}

def parameters(case:str,candidate:str)->dict:
 if case not in CASES or candidate not in CANDIDATES:raise ValueError('Unknown case or candidate')
 return {'case':case,'candidate':candidate,'knobs':BASE|CHANGES[candidate],
         'fallback_trigger':TRIGGERS.get(candidate),
         'source_status':'planned_original_native_or_video_not_observed',
         'law_id':'NRS-484B-270-7a','cell_id':'C111294',
         'comparison_variable':'bicycle_path_intervention',
         'rider_command':'hold_before_motorist_crosses' if case=='witness_1' else 'enter_before_motorist_crosses',
         'intent_asserted':False,
         'intent_physically_verified':False,'legal_interference_verdict':None}

def evaluate_trigger(candidate:str,metrics:dict,source:Path,expected_sha256:str,
                     diagnostic:bool=False)->bool:
 if candidate not in TRIGGERS:raise ValueError('Only fallbacks have triggers')
 raw=source.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=expected_sha256:raise ValueError('Original source hash differs')
 record=json.loads(raw)
 permitted=('original_native_and_video','synthetic_original_shape_emulation') if diagnostic else ('original_native_and_video',)
 if record!=metrics or record.get('source_kind') not in permitted:
  raise ValueError('Metrics are not bound to original Native and video')
 trigger=TRIGGERS[candidate];value=record.get(trigger['metric'])
 if type(value) not in (int,float):raise ValueError('Missing measured fallback metric')
 return value>trigger['threshold'] if trigger['op']=='>' else value<trigger['threshold']
