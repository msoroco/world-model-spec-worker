"""CPU scene request and original-motion observations for backing on a narrow road.

The measured clearance and other-traffic response do not decide reasonable safety.
"""
from __future__ import annotations
from math import hypot


def construct(adapter, *, other_traffic_mps, ego_reverse_mps):
    if other_traffic_mps < 0 or ego_reverse_mps <= 0:
        raise ValueError('invalid engineering speed request')
    road=adapter.road(layout='narrow_road',lanes=2,width_m=5.5)
    ego=adapter.vehicle(role='ego',route=[(20.0,0.0),(4.0,0.0)],gear='reverse',
                        target_mps=ego_reverse_mps)
    other=adapter.vehicle(role='other_traffic',route=[(0.0,0.0),(30.0,0.0)],
                          target_mps=other_traffic_mps)
    return {'road':road,'ego':ego,'other':other}


def measure(samples):
    if len(samples)<3:raise ValueError('original backing span too short')
    rows=[]
    for i,s in enumerate(samples):
        if s.get('frame')!=i or abs(s.get('time_s',-1)-i*.05)>.005:
            raise ValueError('non-20Hz ordered original frames')
        if not s.get('ego_source') or not s.get('other_source') or not s.get('road_source'):
            raise ValueError('original subject, traffic or road source missing')
        if s.get('ego_reverse_gear') is not True:
            raise ValueError('reverse gear readback absent')
        for key in ('ego_xy','other_xy'):
            p=s.get(key)
            if not isinstance(p,list) or len(p)!=2 or any(type(v) not in (int,float) for v in p):
                raise ValueError('original actor position missing')
        if any(type(s.get(k)) not in (int,float) or s[k]<0 for k in ('ego_speed_mps','other_speed_mps')):
            raise ValueError('original actor speed missing')
        rows.append({'frame':i,'ego_x':s['ego_xy'][0],
                     'center_distance_m':hypot(s['ego_xy'][0]-s['other_xy'][0],s['ego_xy'][1]-s['other_xy'][1]),
                     'ego_speed_mps':s['ego_speed_mps'],'other_speed_mps':s['other_speed_mps']})
    if rows[-1]['ego_x']>=rows[0]['ego_x']:
        raise ValueError('measured reverse displacement absent')
    return {'reverse_displacement_m':rows[0]['ego_x']-rows[-1]['ego_x'],
            'min_center_distance_m':min(r['center_distance_m'] for r in rows),
            'other_speed_change_mps':rows[-1]['other_speed_mps']-rows[0]['other_speed_mps'],
            'samples':rows,'legal_safety_judgment':None,'legal_interference_judgment':None}


def audit_comparison(a,b,variable):
    if variable not in ('traffic_clearance','other_traffic_response'):
        raise ValueError('unknown backing comparison')
    if not a.get('samples') or not b.get('samples'):
        raise ValueError('original backing measurements missing')
    for key in ('map_hash','road_hash','camera_plan_hash','duration_s','ego_reverse_mps','other_actor_hash'):
        if not a.get(key) or a[key]!=b.get(key):raise ValueError('fixed condition changed: '+key)
    if variable=='traffic_clearance':
        fixed,varied='other_speed_change_mps','min_center_distance_m'
    else:
        fixed,varied='min_center_distance_m','other_speed_change_mps'
    if abs(a[fixed]-b[fixed])>.001:raise ValueError('held traffic condition changed')
    if abs(a[varied]-b[varied])<.001:raise ValueError('deliberate measured difference absent')
    return {'comparison_complete':True,'fixed_conditions_checked':True,'legal_safety_judgment':None}
