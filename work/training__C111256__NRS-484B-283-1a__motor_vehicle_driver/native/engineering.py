"""Unselected crosswalk travel candidates with distinct source-bound triggers."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

CASES = ('witness_1','witness_2','exception_1_1','exception_1_2')
CANDIDATES = ('primary','fallback1','fallback2','fallback3')
BASE = {'stop_hold_s':0.0, 'route_tracking_lookahead_m':5.0,
        'yield_clearance_margin_s':1.0, 'overview_fov_deg':90.0,
        'rate_hz':20, 'duration_s':24.0,
        'camera_profile':['overview','approach','signal','destination']}
CHANGES = {'primary':{},
           'fallback1':{'route_tracking_lookahead_m':3.0},
           'fallback2':{'yield_clearance_margin_s':2.0},
           'fallback3':{'overview_fov_deg':105.0}}
TRIGGERS = {
    'fallback1':{'metric':'max_route_cross_track_error_m','op':'>','threshold':0.45,
                 'source':'original Native ego pose joined to authored route and map readback'},
    'fallback2':{'metric':'min_ego_half_pedestrian_clearance_s','op':'<','threshold':1.0,
                 'source':'original Native marked-crosswalk pedestrian ego-half occupancy joined to full ego body crossing'},
    'fallback3':{'metric':'min_crosswalk_or_body_pixel_margin_px','op':'<','threshold':40,
                 'source':'decoded original marked-crosswalk and ego-body mask corners in overview video'}}

def parameters(case: str, candidate: str) -> dict:
    if case not in CASES or candidate not in CANDIDATES:
        raise ValueError('Unknown case or candidate')
    return {'case':case,'candidate':candidate,'knobs':BASE|CHANGES[candidate],
            'fallback_trigger':TRIGGERS.get(candidate),
            'source_status':'planned_original_native_or_video_not_observed',
            'law_id':'NRS-484B-283-1a','cell_id':'C111256',
            'comparison_variable':'crosswalk_pedestrian_yield' if case.startswith('witness')
                                  else 'blind_white_cane_exception_applicability',
            'stop_command':'full_halt_before_crosswalk' if case!='witness_2' else 'brief_halt_then_conflict_entry',
            'yield_command':'wait_for_ego_half_pedestrian_clearance' if case!='witness_2'
                            else 'controlled_crosswalk_overlap',
            'exception_declared':'blind_pedestrian_white_cane' if case=='exception_1_2' else 'absent'}

def evaluate_trigger(candidate: str, metrics: dict, source: Path, expected_sha256: str) -> bool:
    if candidate not in TRIGGERS:
        raise ValueError('Only fallbacks have triggers')
    raw=source.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_sha256:
        raise ValueError('Original source hash differs')
    record=json.loads(raw)
    if record!=metrics or record.get('source_kind')!='original_native_and_video':
        raise ValueError('Metrics are not bound to original Native and video')
    trigger=TRIGGERS[candidate]
    value=record.get(trigger['metric'])
    if type(value) not in (int,float):
        raise ValueError('Missing measured fallback metric')
    return value>trigger['threshold'] if trigger['op']=='>' else value<trigger['threshold']
