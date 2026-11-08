"""Deterministic emergency/no-emergency source controls; synthetic CPU only."""
from __future__ import annotations

FRAMES = 480
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def policy(state, candidate):
    if state not in ('emergency', 'routine') or candidate not in CANDIDATES:
        raise ValueError('Unknown exception F control')
    return {
        'state': state, 'candidate_id': candidate, 'source_kind': 'synthetic_cpu_fixture',
        'incident_observation_end_frame': 220 if candidate == 'fallback1' else 180,
        'response_lead_frames': 35 if candidate == 'fallback2' else 20,
        'reference_visibility_override': candidate == 'fallback3',
        'accepted': False,
    }


def incident(state):
    # This packet is authored separately from ego rows. It is never presented
    # as an observed emergency or as an authoritative real-world dispatch.
    return {
        'format': 'synthetic-incident-packet-v1', 'incident_id': 'fixture-incident-001',
        'provenance': 'independent_synthetic_dispatch_fixture',
        'event_kind': 'roadway_medical_response' if state == 'emergency' else 'routine_no_incident',
        'declared_start_frame': 100 if state == 'emergency' else None,
        'declared_end_frame': 240 if state == 'emergency' else None,
        'requested_vehicle_response': state == 'emergency', 'accepted': False,
    }


def rows(state, candidate):
    p = policy(state, candidate)
    packet = incident(state)
    out = []
    for i in range(FRAMES):
        active = state == 'emergency' and 100 <= i < 240
        occupied = state == 'emergency' and 120 <= i < 190
        x = round(-20 + i * .08, 4)
        y = -4.0 if occupied else -1.5
        body = [[round(x-2.5,4),y-.85],[round(x+2.5,4),y-.85],
                [round(x+2.5,4),y+.85],[round(x-2.5,4),y+.85]]
        out.append({
            'native_frame': 2000+i, 'time_s': round(i/20,2),
            'ego_center_xy': [x,y], 'ego_body_xy': body,
            'incident_id': packet['incident_id'] if active else None,
            'incident_active': active, 'bicycle_lane_body_occupied': occupied,
            'scripted_reference_visible': p['reference_visibility_override'] or i%10 != 0,
            'synthetic_diagnostic': True,
        })
    return out


def measure(samples, packet, p):
    if len(samples) != FRAMES or packet['format'] != 'synthetic-incident-packet-v1':
        raise ValueError('Source duration or incident packet changed')
    if packet['provenance'] != 'independent_synthetic_dispatch_fixture':
        raise ValueError('Incident provenance changed')
    expected = p['state'] == 'emergency'
    if packet['requested_vehicle_response'] is not expected:
        raise ValueError('Incident response mismatch')
    if (packet['declared_start_frame'], packet['declared_end_frame']) != ((100,240) if expected else (None,None)):
        raise ValueError('Incident interval changed')
    for i,r in enumerate(samples):
        if r['native_frame'] != 2000+i or r['time_s'] != round(i/20,2):
            raise ValueError('Source frame/time changed')
        active = expected and 100 <= i < 240
        occupied = expected and 120 <= i < 190
        if r['incident_active'] is not active or r['incident_id'] != (packet['incident_id'] if active else None):
            raise ValueError('Incident/source join changed')
        if r['bicycle_lane_body_occupied'] is not occupied:
            raise ValueError('Occupancy annotation changed')
        if (r['ego_center_xy'][1] == -4.0) is not occupied:
            raise ValueError('Body path/occupancy mismatch')
        if r['ego_body_xy'] != [[round(r['ego_center_xy'][0]-2.5,4),r['ego_center_xy'][1]-.85],
                                [round(r['ego_center_xy'][0]+2.5,4),r['ego_center_xy'][1]-.85],
                                [round(r['ego_center_xy'][0]+2.5,4),r['ego_center_xy'][1]+.85],
                                [round(r['ego_center_xy'][0]-2.5,4),r['ego_center_xy'][1]+.85]]:
            raise ValueError('Body footprint changed')
    occupied = sum(r['bicycle_lane_body_occupied'] for r in samples)
    joined = sum(r['incident_active'] and r['bicycle_lane_body_occupied'] for r in samples)
    return {'state':p['state'],'candidate_id':p['candidate_id'],
            'incident_active_frames':sum(r['incident_active'] for r in samples),
            'occupied_frames':occupied,'incident_occupied_frames':joined,
            'synthetic_temporal_join':expected and joined==70,
            'original_native_emergency_verified':False,'legal_exception_verified':False,'accepted':False}


def triggers(samples,p):
    observed=sum(r['incident_active'] for r in samples[:p['incident_observation_end_frame']])
    visible=round(sum(r['scripted_reference_visible'] for r in samples[100:171])/71,6)
    return {'incident_observation_frames':observed,
            'response_lead_frames':p['response_lead_frames'],
            'scripted_reference_visible_fraction':visible,
            'fallback1_trigger':observed<100 if p['state']=='emergency' else None,
            'fallback2_trigger':p['response_lead_frames']<30,
            'fallback3_trigger':visible<.95,
            'original_camera_pixels_verified':False}
