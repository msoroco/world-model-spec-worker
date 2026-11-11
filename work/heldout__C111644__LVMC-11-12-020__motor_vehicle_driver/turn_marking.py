"""Authorized intersection turn-course indication construction and observations."""
from __future__ import annotations
from math import hypot


def construct(adapter, indication_type, route_variant):
    if indication_type not in ('marker','button','other_indication') or route_variant not in ('follow','depart'):
        raise ValueError('unknown indication or route variant')
    intersection=adapter.intersection(layout='intersection',maneuver='turn')
    course=[(-20,0),(-5,0),(0,5),(0,20)]
    indication=adapter.turn_course_indication(kind=indication_type,authorized=True,
                                               within_intersection=True,course_xy=course)
    route=course if route_variant=='follow' else [(-20,0),(-5,0),(5,5),(5,20)]
    ego=adapter.vehicle(role='ego',route=route,target_mps=3)
    return {'intersection':intersection,'indication':indication,'ego':ego}


def _segment_distance(p,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1]
    d=dx*dx+dy*dy
    if d<.001:raise ValueError('degenerate indicated course segment')
    t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/d))
    return hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)


def measure(indication,frames):
    if indication.get('kind') not in ('marker','button','other_indication'):
        raise ValueError('indication type missing')
    if indication.get('authorized') is not True or indication.get('within_intersection') is not True or not indication.get('authorization_source'):
        raise ValueError('authorized in-intersection indication source missing')
    course=indication.get('course_xy')
    if not isinstance(course,list) or len(course)<3:
        raise ValueError('indicated course geometry missing')
    if not isinstance(frames,list) or len(frames)<3:raise ValueError('original turn motion missing')
    rows=[]
    for i,f in enumerate(frames):
        if f.get('frame')!=i or abs(f.get('time_s',-1)-i*.05)>.005 or not f.get('subject_source'):
            raise ValueError('original synchronized subject source missing')
        p=f.get('subject_center_xy')
        if not isinstance(p,list) or len(p)!=2:raise ValueError('original subject position missing')
        rows.append({'frame':i,'distance_to_indicated_course_m':min(_segment_distance(p,a,b) for a,b in zip(course,course[1:]))})
    return {'indication_type':indication['kind'],'max_center_deviation_m':max(r['distance_to_indicated_course_m'] for r in rows),
            'samples':rows,'legal_obedience_judgment':None}


def audit_comparison(a,b,variable):
    if variable not in ('route_response','indication_form') or not a.get('samples') or not b.get('samples'):
        raise ValueError('valid two-case comparison requires original measurements')
    for key in ('intersection_hash','course_hash','camera_plan_hash','duration_s','subject_hash'):
        if not a.get(key) or a[key]!=b.get(key):raise ValueError('fixed condition changed: '+key)
    fixed,varied=('indication_type','max_center_deviation_m') if variable=='route_response' else ('max_center_deviation_m','indication_type')
    if a.get(fixed)!=b.get(fixed):raise ValueError('held condition changed: '+fixed)
    if a.get(varied)==b.get(varied):raise ValueError('deliberate difference absent')
    return {'comparison_complete':True,'fixed_conditions_checked':True,'legal_obedience_judgment':None}
