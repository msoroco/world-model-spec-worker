"""Three-lane scene requests and original lane occupancy observations."""
from __future__ import annotations

CASES={
 'right_baseline':('right','none'), 'left_travel':('left','none'), 'center_no_exception':('center','none'),
 'center_pass_clear':('center','passing_clear'), 'center_pass_occluded':('center','passing_occluded'),
 'center_prepare_left':('center','left_turn_preparation'),
 'center_allocated_signed':('center','allocated_signed'),
 'center_allocated_unsigned':('center','allocated_unsigned'),
}

def construct(adapter,case_name):
    if case_name not in CASES:raise ValueError('unknown three-lane exact case')
    lane,variant=CASES[case_name]
    road=adapter.road(layout='three_lane_road',clearly_marked_lanes=3)
    marks=[adapter.lane_marking(road=road,boundary=i) for i in (0,1,2,3)]
    features=[]
    if variant.startswith('passing'):
        features.append(adapter.vehicle(role='passed_vehicle',lane='right',target_mps=2))
        if variant=='passing_occluded':
            features.append(adapter.occluder(role='sight_block',position_m=55,height_m=2.5))
    elif variant=='left_turn_preparation':
        features.append(adapter.turn_route(origin_lane='center',direction='left'))
    elif variant.startswith('allocated'):
        features.append(adapter.lane_allocation(lane='center',direction='ego_direction'))
        if variant=='allocated_signed':features.append(adapter.sign(type='center_lane_allocation',direction='ego_direction'))
    ego=adapter.vehicle(role='ego',lane=lane,target_mps=4)
    return {'road':road,'lane_markings':marks,'features':features,'ego':ego}

def measure(context,frames):
    if context.get('marked_lane_count')!=3 or not context.get('marking_source') or not context.get('allocation_source'):
        raise ValueError('original three-lane markings or allocation source missing')
    if context.get('exception_variant') not in ('none','passing_clear','passing_occluded','left_turn_preparation','allocated_signed','allocated_unsigned'):
        raise ValueError('exception premise missing')
    if context.get('exception_variant').startswith('passing') and (not context.get('passing_source') or not context.get('sight_source')):
        raise ValueError('passing and sight source required')
    if context.get('exception_variant').startswith('allocated') and not context.get('sign_source'):
        raise ValueError('posted allocation sign source required')
    if not isinstance(frames,list) or len(frames)<2:raise ValueError('original lane frames missing')
    rows=[]
    for i,r in enumerate(frames):
        if r.get('frame')!=i or r.get('lane') not in ('right','center','left') or not r.get('body_source'):
            raise ValueError('original body lane frame missing')
        rows.append({'frame':i,'lane':r['lane']})
    return {'exception_variant':context['exception_variant'],
            'occupied_lanes':sorted(set(r['lane'] for r in rows)),
            'extreme_left_occupied':any(r['lane']=='left' for r in rows),
            'center_occupied':any(r['lane']=='center' for r in rows),
            'samples':rows,'legal_lane_judgment':None}

def audit_comparison(a,b,variable):
    if variable not in ('lane_occupancy','passing_visibility','turn_preparation','allocation_sign') or not a.get('samples') or not b.get('samples'):
        raise ValueError('original two-case lane comparison required')
    for key in ('road_hash','marking_hash','camera_plan_hash','duration_s','actor_hash'):
        if not a.get(key) or a[key]!=b.get(key):raise ValueError('fixed condition changed: '+key)
    varied='occupied_lanes' if variable=='lane_occupancy' else 'exception_variant'
    fixed='exception_variant' if variable=='lane_occupancy' else 'occupied_lanes'
    if a.get(fixed)!=b.get(fixed):raise ValueError('held condition changed: '+fixed)
    if a.get(varied)==b.get(varied):raise ValueError('deliberate difference absent')
    return {'comparison_complete':True,'variable':variable,'legal_lane_judgment':None}
