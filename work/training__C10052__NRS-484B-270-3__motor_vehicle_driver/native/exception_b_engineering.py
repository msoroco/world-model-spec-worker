"""Synthetic CPU controls for NRS 484B.270(3)(b) disabled-vehicle clause.

A source-coded propulsion fault is an engineering condition, not a legal finding
that an original Native vehicle was disabled or being operated/parked under law.
"""
from __future__ import annotations
import math

FRAMES=480
NAMES=('primary','fallback1','fallback2','fallback3')
BIKE=[[-15,-5],[20,-5],[20,-3],[-15,-3]]

def policy(state,candidate):
    if state not in ('faulted','healthy') or candidate not in NAMES:
        raise ValueError('Unknown disabled-vehicle construction')
    return {'case_suffix':'exception_b_'+state,'candidate_id':candidate,
        'state':state,'fault_start_frame':80,'fault_end_frame':360,
        'observation_end_frame':300 if candidate=='fallback1' else 240,
        'propulsion_test_end_frame':190 if candidate=='fallback2' else 160,
        'reference_visibility_override':candidate=='fallback3',
        'source_kind':'synthetic_cpu_fixture','accepted':False}

def polygon(x,y=-4.0):
    return [[round(x-2.6,4),y-.9],[round(x+2.6,4),y-.9],
            [round(x+2.6,4),y+.9],[round(x-2.6,4),y+.9]]

def area(a,b):
    ax0=min(p[0] for p in a);ax1=max(p[0] for p in a)
    ay0=min(p[1] for p in a);ay1=max(p[1] for p in a)
    bx0=min(p[0] for p in b);bx1=max(p[0] for p in b)
    by0=min(p[1] for p in b);by1=max(p[1] for p in b)
    return max(0,min(ax1,bx1)-max(ax0,bx0))*max(0,min(ay1,by1)-max(ay0,by0))

def rows(state,candidate):
    p=policy(state,candidate);out=[]
    for i in range(FRAMES):
        commanded=.45 if 100<=i<p['propulsion_test_end_frame'] else 0.0
        fault=state=='faulted' and p['fault_start_frame']<=i<p['fault_end_frame']
        # Deterministic measured-response fixture: identical command under
        # fault/healthy controls, with healthy motion after propulsion request.
        x=0.0 if fault else round(max(0,i-100)*.12,4)
        if state=='healthy' and i<100:x=0.0
        if state=='faulted' and i>=p['fault_end_frame']:x=round((i-p['fault_end_frame'])*.12,4)
        out.append({'native_frame':2000+i,'time_s':round(i/20,2),
            'ego_center_xy':[x,-4.0],'ego_body_xy':polygon(x),
            'throttle_command':commanded,'brake_command':0.0 if commanded else 1.0,
            'fault_injection_applied':fault,
            'powertrain_readback':{'drive_enabled':not fault,
                'fault_code':'synthetic_propulsion_disabled' if fault else None},
            'scripted_reference_visible':p['reference_visibility_override'] or i%10!=0,
            'synthetic_diagnostic':True})
    return out

def measure(samples,p):
    if len(samples)!=FRAMES:raise ValueError('Source duration changed')
    for i,r in enumerate(samples):
        if r['native_frame']!=2000+i or r['time_s']!=round(i/20,2):
            raise ValueError('Source frame/time changed')
        if r['powertrain_readback']['drive_enabled']==r['fault_injection_applied']:
            raise ValueError('Fault/readback contradiction')
        if (r['powertrain_readback']['fault_code']=='synthetic_propulsion_disabled') != r['fault_injection_applied']:
            raise ValueError('Fault code/readback contradiction')
        if r['throttle_command'] not in (0.0,.45) or r['brake_command'] not in (0.0,1.0):
            raise ValueError('Control source changed')
        if not all(math.isfinite(v) for point in r['ego_body_xy'] for v in point):
            raise ValueError('Invalid body')
    test=[r for r in samples[100:p['propulsion_test_end_frame']]
          if r['throttle_command']>=.4 and r['brake_command']==0]
    if len(test)<60:raise ValueError('Propulsion test incomplete')
    fault_frames=sum(r['fault_injection_applied'] for r in samples)
    movement=round(test[-1]['ego_center_xy'][0]-test[0]['ego_center_xy'][0],4)
    occupancy=sum(area(r['ego_body_xy'],BIKE)>0 for r in samples[100:240])
    result={'case_suffix':p['case_suffix'],'candidate_id':p['candidate_id'],
        'fault_readback_frames':fault_frames,'propulsion_test_frames':len(test),
        'propulsion_test_displacement_m':movement,
        'bicycle_lane_occupied_frames_100_240':occupancy,
        'synthetic_fault_response':p['state']=='faulted' and fault_frames==280 and movement==0,
        'original_native_disabled_state_verified':False,
        'legal_exception_verified':False,'accepted':False}
    if p['state']=='healthy' and (fault_frames or movement<=5):
        raise ValueError('Healthy control did not move under propulsion')
    if p['state']=='faulted' and not result['synthetic_fault_response']:
        raise ValueError('Faulted control did not retain source-bound immobilization')
    return result

def triggers(samples,p):
    readback=sum(r['fault_injection_applied'] for r in samples[:p['observation_end_frame']])
    test=sum(r['throttle_command']>=.4 for r in samples[:p['propulsion_test_end_frame']])
    visible=round(sum(r['scripted_reference_visible'] for r in samples[100:171])/71,6)
    return {'case_suffix':p['case_suffix'],'candidate_id':p['candidate_id'],
        'fault_observation_frames':readback,'propulsion_test_frames':test,
        'scripted_reference_visible_fraction':visible,
        'fallback1_trigger':readback<200 if p['state']=='faulted' else None,
        'fallback2_trigger':test<75,
        'fallback3_trigger':visible<.95,
        'original_camera_pixels_verified':False}
