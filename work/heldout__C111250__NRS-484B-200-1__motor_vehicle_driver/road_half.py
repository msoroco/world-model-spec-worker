"""Road-half scene variants and original body position for NRS 484B.200(1)."""
from __future__ import annotations
from math import hypot

EXCEPTIONS=('none','overtaking_same_direction','right_half_closed','three_lanes','posted_one_way','insufficient_width')

def construct(adapter,exception,body_side):
    if exception not in EXCEPTIONS or body_side not in ('right','left'):
        raise ValueError('unknown exact road-half variant')
    lanes=3 if exception=='three_lanes' else (1 if exception=='posted_one_way' else 2)
    width=3.0 if exception=='insufficient_width' else 7.0
    road=adapter.road(layout='intersection',lanes=lanes,width_m=width,one_way=exception=='posted_one_way')
    features=[]
    if exception=='overtaking_same_direction':
        features.append(adapter.vehicle(role='passed_vehicle',route=[(-20,-1),(20,-1)],target_mps=2))
    if exception=='right_half_closed':
        features.append(adapter.closure(road=road,side='right',begin_m=-10,end_m=10))
    if exception=='posted_one_way':
        features.append(adapter.sign(type='one_way',road=road))
    ego=adapter.vehicle(role='ego',route=[(-25,1 if body_side=='left' else -1),(25,1 if body_side=='left' else -1)],target_mps=4)
    return {'road':road,'features':features,'ego':ego}

def _signed(point,line):
    a,b=line;dx,dy=b[0]-a[0],b[1]-a[1];d=hypot(dx,dy)
    if d<1:raise ValueError('degenerate original road centerline')
    return (dx*(point[1]-a[1])-dy*(point[0]-a[0]))/d

def measure(context,frames):
    if context.get('exception') not in EXCEPTIONS or not context.get('exception_source') or not context.get('road_source'):
        raise ValueError('sourced road exception premise missing')
    line=context.get('centerline')
    if not isinstance(line,list) or len(line)!=2:raise ValueError('original road centerline missing')
    if not isinstance(frames,list) or len(frames)<2:raise ValueError('original body frames missing')
    rows=[]
    for i,f in enumerate(frames):
        if f.get('frame')!=i or not f.get('body_source'):
            raise ValueError('original body frame or source missing')
        corners=f.get('ground_corners')
        if not isinstance(corners,list) or len(corners)!=4:raise ValueError('four original body corners required')
        sides=[_signed(p,line) for p in corners]
        rows.append({'frame':i,'min_signed_m':min(sides),'max_signed_m':max(sides)})
    return {'exception':context['exception'],'min_signed_m':min(r['min_signed_m'] for r in rows),
            'max_signed_m':max(r['max_signed_m'] for r in rows),
            'any_left_half_body':any(r['max_signed_m']>0 for r in rows),'samples':rows,'legal_exception_judgment':None}

def audit_comparison(a,b,variable):
    if variable not in ('body_side','exception_premise') or not a.get('samples') or not b.get('samples'):
        raise ValueError('original two-case road-half measurements required')
    keys=('road_hash','centerline_hash','camera_plan_hash','duration_s','actor_hash') if variable=='body_side' else ('centerline_hash','camera_plan_hash','duration_s','actor_hash')
    for key in keys:
        if not a.get(key) or a[key]!=b.get(key):raise ValueError('fixed condition changed: '+key)
    fixed,varied=('exception','any_left_half_body') if variable=='body_side' else ('any_left_half_body','exception')
    if a.get(fixed)!=b.get(fixed):raise ValueError('held condition changed: '+fixed)
    if a.get(varied)==b.get(varied):raise ValueError('deliberate difference absent')
    return {'comparison_complete':True,'legal_exception_judgment':None}
