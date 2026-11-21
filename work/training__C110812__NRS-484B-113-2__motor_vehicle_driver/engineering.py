"""Four distinct same-law corner candidates and source-measured fallback gates."""
from __future__ import annotations
import hashlib,json,math
from pathlib import Path
from controller import ReverseKnobs
CASES=('condition_a','condition_b')
CANDIDATES=('primary','fallback1','fallback2','fallback3')
BASE={'steering_gain':.35,'brake_margin_m':.10,'overview_fov_deg':90,'rate_hz':20,'duration_s':24}
CHANGES={'primary':{},'fallback1':{'steering_gain':.55},
         'fallback2':{'brake_margin_m':.4},'fallback3':{'overview_fov_deg':105}}
TRIGGERS={
 'fallback1':{'metric':'max_reverse_corner_heading_error_deg','op':'>','threshold':12,
              'source':'original Native pose and surveyed corner-route heading'},
 'fallback2':{'metric':'reverse_endpoint_overshoot_m','op':'>','threshold':.20,
              'source':'original Native center/body relative to route endpoint'},
 'fallback3':{'metric':'min_reverse_body_pixel_margin_px','op':'<','threshold':40,
              'source':'decoded original overview video and body mask'}}
def parameters(case,candidate):
    if case not in CASES or candidate not in CANDIDATES:raise ValueError('Unknown case/candidate')
    return {'case':case,'candidate':candidate,'knobs':BASE|CHANGES[candidate],
            'fallback_trigger':TRIGGERS.get(candidate),'source_status':'original Native and pixels pending'}
def controller_parameters(case,candidate):
    knobs=parameters(case,candidate)['knobs']
    return ReverseKnobs(steering_gain=knobs['steering_gain'],brake_margin_m=knobs['brake_margin_m'])
def evaluate_trigger(candidate,source:Path,expected_sha256):
    if candidate not in TRIGGERS:raise ValueError('Only fallback trigger is measurable')
    raw=source.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_sha256:raise ValueError('Original trigger source hash differs')
    record=json.loads(raw)
    if record.get('source_kind')!='original_native_and_video':raise ValueError('Trigger source is not original Native/video')
    trigger=TRIGGERS[candidate];value=record.get(trigger['metric'])
    if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('Measured trigger metric absent')
    return value>trigger['threshold'] if trigger['op']=='>' else value<trigger['threshold']
