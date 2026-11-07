"""Unselected two-cycle motorcycle engineering with source-bound triggers."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path

CASES = ('condition_a','condition_b')
CANDIDATES = ('primary','fallback1','fallback2','fallback3')
BASE = {'stop_hold_s':1.5, 'route_tracking_lookahead_m':5.0,
        'yield_clearance_margin_s':1.0, 'overview_fov_deg':90.0,
        'cross_signal_green_frames':80,'cross_signal_yellow_frames':20,
        'cross_signal_all_red_frames':20,
        'rate_hz':20, 'duration_s':24.0,
        'camera_profile':['overview','approach','signal','destination']}
CHANGES = {'primary':{},
           'fallback1':{'route_tracking_lookahead_m':3.0},
           'fallback2':{'cross_signal_green_frames':70},
           'fallback3':{'overview_fov_deg':105.0}}
TRIGGERS = {
    'fallback1':{'metric':'max_route_cross_track_error_m','op':'>','threshold':0.45,
                 'source':'original Native ego pose joined to authored route and map readback'},
    'fallback2':{'metric':'second_complete_cross_cycle_frame','op':'>','threshold':280,
                 'source':'original Native cross-signal state transitions joined to ego red and capture frames'},
    'fallback3':{'metric':'min_signal_or_body_pixel_margin_px','op':'<','threshold':40,
                 'source':'decoded original signal and body mask corners in overview video'}}

def parameters(case: str, candidate: str) -> dict:
    if case not in CASES or candidate not in CANDIDATES:
        raise ValueError('Unknown case or candidate')
    return {'case':case,'candidate':candidate,'knobs':BASE|CHANGES[candidate],
            'fallback_trigger':TRIGGERS.get(candidate),
            'source_status':'planned_original_native_or_video_not_observed',
            'law_id':'NRS-484B-307-8d','cell_id':'C110919',
            'comparison_variable':'two_complete_signal_cycles_waited_before_right_turn',
            'stop_command':'complete_halt',
            'cycle_wait_target':2 if case=='condition_a' else 1,
            'fault_injection':'hold_ego_red_and_withhold_detector_request',
            'yield_command':'wait_for_pedestrian_clearance'}

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
    if type(value) not in (int,float) or not math.isfinite(value) or value < 0:
        raise ValueError('Missing measured fallback metric')
    return value>trigger['threshold'] if trigger['op']=='>' else value<trigger['threshold']
