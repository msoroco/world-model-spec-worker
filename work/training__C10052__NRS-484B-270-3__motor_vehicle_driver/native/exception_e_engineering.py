"""Synthetic police-direction and no-direction controls for NRS 484B.270(3)(e)."""
from __future__ import annotations

FRAMES=480
CANDIDATES=('primary','fallback1','fallback2','fallback3')
OFFICER='fixture-officer-12'
VEHICLE='fixture-driver-vehicle-17'
COMMAND='enter_bicycle_lane'

def policy(state,candidate):
    if state not in ('directed','routine') or candidate not in CANDIDATES:
        raise ValueError('Unknown police-direction control')
    return {'state':state,'candidate_id':candidate,
        'direction_observation_end_frame':220 if candidate=='fallback1' else 180,
        'response_lead_frames':35 if candidate=='fallback2' else 20,
        'reference_visibility_override':candidate=='fallback3',
        'source_kind':'synthetic_cpu_fixture','accepted':False}

def direction(state):
    directed=state=='directed'
    return {'format':'synthetic-police-direction-v1',
        'direction_id':'fixture-direction-001',
        'issuer':'synthetic_traffic_officer_actor',
        'officer_id':OFFICER if directed else None,
        'addressed_vehicle_id':VEHICLE if directed else None,
        'command':COMMAND if directed else None,
        'start_frame':100 if directed else None,
        'end_frame':240 if directed else None,
        'active':directed,'accepted':False}

def rows(state,candidate):
    p=policy(state,candidate);out=[]
    for i in range(FRAMES):
        active=state=='directed' and 100<=i<240
        occupied=state=='directed' and 120<=i<190
        x=round(-20+i*.08,4);y=-4.0 if occupied else -1.5
        body=[[round(x-2.5,4),y-.85],[round(x+2.5,4),y-.85],
              [round(x+2.5,4),y+.85],[round(x-2.5,4),y+.85]]
        out.append({'native_frame':3000+i,'time_s':round(i/20,2),
            'ego_center_xy':[x,y],'ego_body_xy':body,
            'vehicle_id':VEHICLE,
            'officer_id':OFFICER if active else None,
            'direction_id':'fixture-direction-001' if active else None,
            'packet_command':COMMAND if active else None,
            'direction_active':active,
            'driver_response':'lane_enter' if occupied else 'lane_clear',
            'bicycle_lane_body_occupied':occupied,
            'scripted_reference_visible':p['reference_visibility_override'] or i%10!=0,
            'synthetic_diagnostic':True})
    return out

def measure(samples,packet,p):
    if len(samples)!=FRAMES or packet.get('format')!='synthetic-police-direction-v1':
        raise ValueError('Direction source duration or packet changed')
    if packet.get('issuer')!='synthetic_traffic_officer_actor':
        raise ValueError('Officer packet issuer changed')
    expected=p['state']=='directed'
    if packet.get('active') is not expected or \
       (packet.get('start_frame'),packet.get('end_frame'))!=((100,240) if expected else (None,None)):
        raise ValueError('Officer direction interval changed')
    if packet.get('direction_id')!='fixture-direction-001' or \
       packet.get('officer_id')!=(OFFICER if expected else None) or \
       packet.get('addressed_vehicle_id')!=(VEHICLE if expected else None) or \
       packet.get('command')!=(COMMAND if expected else None):
        raise ValueError('Officer identity, addressee or command changed')
    for i,r in enumerate(samples):
        active=expected and 100<=i<240
        occupied=expected and 120<=i<190
        if r['native_frame']!=3000+i or r['time_s']!=round(i/20,2):
            raise ValueError('Direction frame/time changed')
        if r['vehicle_id']!=VEHICLE or r['officer_id']!=(OFFICER if active else None):
            raise ValueError('Officer/driver identity changed')
        if r['direction_id']!=('fixture-direction-001' if active else None) or \
           r['packet_command']!=(COMMAND if active else None) or \
           r['direction_active'] is not active:
            raise ValueError('Direction/source join changed')
        if r['driver_response']!=('lane_enter' if occupied else 'lane_clear') or \
           r['bicycle_lane_body_occupied'] is not occupied or \
           (r['ego_center_xy'][1]==-4.0) is not occupied:
            raise ValueError('Driver response/occupancy changed')
        x,y=r['ego_center_xy']
        if r['ego_body_xy']!=[[round(x-2.5,4),y-.85],[round(x+2.5,4),y-.85],
                            [round(x+2.5,4),y+.85],[round(x-2.5,4),y+.85]]:
            raise ValueError('Driver body footprint changed')
    active=sum(r['direction_active'] for r in samples)
    occupied=sum(r['bicycle_lane_body_occupied'] for r in samples)
    joined=sum(r['direction_active'] and r['bicycle_lane_body_occupied'] for r in samples)
    return {'state':p['state'],'candidate_id':p['candidate_id'],
        'direction_active_frames':active,'occupied_frames':occupied,
        'direction_response_frames':joined,
        'original_native_police_direction_verified':False,
        'legal_compliance_verified':False,'accepted':False}

def triggers(samples,p):
    observed=sum(r['direction_active'] for r in samples[:p['direction_observation_end_frame']])
    visible=round(sum(r['scripted_reference_visible'] for r in samples[100:171])/71,6)
    return {'direction_observation_frames':observed,
        'response_lead_frames':p['response_lead_frames'],
        'scripted_reference_visible_fraction':visible,
        'fallback1_trigger':observed<100 if p['state']=='directed' else None,
        'fallback2_trigger':p['response_lead_frames']<30,
        'fallback3_trigger':visible<.95,
        'original_camera_pixels_verified':False}
