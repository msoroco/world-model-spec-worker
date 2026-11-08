"""Synthetic duty-assignment and routine controls for NRS 484B.270(3)(d)."""
from __future__ import annotations

FRAMES=480
CANDIDATES=('primary','fallback1','fallback2','fallback3')
VEHICLE='fixture-service-vehicle-17'
OPERATOR='fixture-operator-04'

def policy(state,candidate):
    if state not in ('duty','routine') or candidate not in CANDIDATES:
        raise ValueError('Unknown official-duty control')
    return {'state':state,'candidate_id':candidate,
        'duty_observation_end_frame':220 if candidate=='fallback1' else 180,
        'response_lead_frames':35 if candidate=='fallback2' else 20,
        'reference_visibility_override':candidate=='fallback3',
        'source_kind':'synthetic_cpu_fixture','accepted':False}

def assignment(state):
    return {'format':'synthetic-duty-assignment-v1',
        'assignment_id':'fixture-duty-001','issuer':'synthetic_public_works_dispatch',
        'task':'bicycle_facility_surface_inspection' if state=='duty' else 'none',
        'authorized_vehicle_id':VEHICLE if state=='duty' else None,
        'authorized_operator_id':OPERATOR if state=='duty' else None,
        'start_frame':100 if state=='duty' else None,
        'end_frame':240 if state=='duty' else None,
        'active':state=='duty','accepted':False}

def rows(state,candidate):
    p=policy(state,candidate);out=[]
    for i in range(FRAMES):
        active=state=='duty' and 100<=i<240
        occupied=state=='duty' and 120<=i<190
        x=round(-20+i*.08,4);y=-4.0 if occupied else -1.5
        body=[[round(x-2.5,4),y-.85],[round(x+2.5,4),y-.85],
              [round(x+2.5,4),y+.85],[round(x-2.5,4),y+.85]]
        out.append({'native_frame':3000+i,'time_s':round(i/20,2),
            'ego_center_xy':[x,y],'ego_body_xy':body,
            'vehicle_id':VEHICLE,'operator_id':OPERATOR,
            'assignment_id':'fixture-duty-001' if active else None,
            'duty_active':active,'bicycle_lane_body_occupied':occupied,
            'scripted_reference_visible':p['reference_visibility_override'] or i%10!=0,
            'synthetic_diagnostic':True})
    return out

def measure(samples,packet,p):
    if len(samples)!=FRAMES or packet.get('format')!='synthetic-duty-assignment-v1':
        raise ValueError('Duty source duration or packet changed')
    if packet.get('issuer')!='synthetic_public_works_dispatch':
        raise ValueError('Duty packet issuer changed')
    expected=p['state']=='duty'
    if packet.get('active') is not expected or \
       (packet.get('start_frame'),packet.get('end_frame'))!=((100,240) if expected else (None,None)):
        raise ValueError('Duty interval changed')
    if packet.get('task')!=('bicycle_facility_surface_inspection' if expected else 'none') or \
       packet.get('authorized_vehicle_id')!=(VEHICLE if expected else None) or \
       packet.get('authorized_operator_id')!=(OPERATOR if expected else None):
        raise ValueError('Duty authorization changed')
    for i,r in enumerate(samples):
        active=expected and 100<=i<240
        occupied=expected and 120<=i<190
        if r['native_frame']!=3000+i or r['time_s']!=round(i/20,2):
            raise ValueError('Duty frame/time changed')
        if (r['vehicle_id'],r['operator_id'])!=(VEHICLE,OPERATOR):
            raise ValueError('Duty actor identity changed')
        if r['assignment_id']!=('fixture-duty-001' if active else None) or r['duty_active'] is not active:
            raise ValueError('Duty assignment/source join changed')
        if r['bicycle_lane_body_occupied'] is not occupied or \
           (r['ego_center_xy'][1]==-4.0) is not occupied:
            raise ValueError('Duty response/body occupancy changed')
        x,y=r['ego_center_xy']
        if r['ego_body_xy']!=[[round(x-2.5,4),y-.85],[round(x+2.5,4),y-.85],
                            [round(x+2.5,4),y+.85],[round(x-2.5,4),y+.85]]:
            raise ValueError('Duty body footprint changed')
    active=sum(r['duty_active'] for r in samples)
    occupied=sum(r['bicycle_lane_body_occupied'] for r in samples)
    joined=sum(r['duty_active'] and r['bicycle_lane_body_occupied'] for r in samples)
    return {'state':p['state'],'candidate_id':p['candidate_id'],
            'duty_active_frames':active,'occupied_frames':occupied,
            'duty_occupied_frames':joined,
            'original_native_official_duty_verified':False,
            'legal_exception_verified':False,'accepted':False}

def triggers(samples,p):
    observed=sum(r['duty_active'] for r in samples[:p['duty_observation_end_frame']])
    visible=round(sum(r['scripted_reference_visible'] for r in samples[100:171])/71,6)
    return {'duty_observation_frames':observed,
        'response_lead_frames':p['response_lead_frames'],
        'scripted_reference_visible_fraction':visible,
        'fallback1_trigger':observed<100 if p['state']=='duty' else None,
        'fallback2_trigger':p['response_lead_frames']<30,
        'fallback3_trigger':visible<.95,
        'original_camera_pixels_verified':False}
