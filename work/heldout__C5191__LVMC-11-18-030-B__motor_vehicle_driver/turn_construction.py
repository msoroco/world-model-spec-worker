"""CARLA-lazy connected marked approach and left-turn construction for C5191."""
from math import atan2, degrees, hypot, isfinite, pi

CASES = ('left_turn_lane_contained_approach',
         'left_turn_early_boundary_crossing_no_signal',
         'left_turn_early_boundary_crossing_signaled')

def _xy(waypoint):
    location = waypoint.transform.location
    out = float(location.x), float(location.y)
    if not all(map(isfinite, out)):
        raise ValueError('Nonfinite Native waypoint')
    return out

def _heading(waypoint):
    vector = waypoint.transform.get_forward_vector()
    x,y=float(vector.x),float(vector.y)
    if not all(map(isfinite,(x,y))) or hypot(x,y)<.1:
        raise ValueError('Invalid Native heading')
    return atan2(y,x)

def _driving(wp):
    return wp is not None and 'driving' in str(wp.lane_type).lower()

def _marked(wp):
    return all(x is not None and str(x.type).rsplit('.',1)[-1].lower()!='none'
               for x in (getattr(wp,'left_lane_marking',None),getattr(wp,'right_lane_marking',None)))

def _chain(start,spacing,steps):
    out=[start]
    for _ in range(steps):
        current=out[-1]
        successors=[w for w in current.next(spacing) if _driving(w) and _marked(w)
                    and not w.is_junction and (w.road_id,w.lane_id)==(current.road_id,current.lane_id)]
        if len(successors)!=1:
            raise ValueError('Marked approach lacks unique connected continuation')
        out.append(successors[0])
    return out

def select_marked_left_scene(carla_map, *, spacing_m=2., approach_steps=12,
                             candidate_index=0):
    if not (isfinite(spacing_m) and spacing_m>0) or type(approach_steps) is not int or approach_steps<4:
        raise ValueError('Invalid Native turn route sampling')
    options=[]
    for start in carla_map.generate_waypoints(spacing_m):
        if not _driving(start) or start.is_junction or not _marked(start):continue
        left=start.get_left_lane()
        if not (_driving(left) and not left.is_junction and _marked(left) and
                left.road_id==start.road_id and left.lane_id*start.lane_id>0):continue
        try:approach=_chain(start,spacing_m,approach_steps);adjacent=_chain(left,spacing_m,approach_steps)
        except ValueError:continue
        if any(a.road_id!=b.road_id or a.lane_id*b.lane_id<=0 for a,b in zip(approach,adjacent)):
            continue
        if any(hypot(*[a-b for a,b in zip(_xy(x),_xy(y))])<.5 for x,y in zip(approach,adjacent)):
            continue
        for junction in approach[-1].next(spacing_m):
            if not _driving(junction) or not junction.is_junction:continue
            for exit_wp in junction.next(8.):
                if not _driving(exit_wp) or exit_wp.is_junction or not _marked(exit_wp):continue
                angle=degrees((_heading(exit_wp)-_heading(approach[-1])+pi)%(2*pi)-pi)
                if 45<=angle<=135:
                    options.append((int(start.road_id),int(start.lane_id),*_xy(start),
                                    {'approach':approach,'adjacent':adjacent,'junction':junction,
                                     'exit':exit_wp,'approach_road_id':int(start.road_id),
                                     'approach_lane_id':int(start.lane_id),
                                     'adjacent_lane_id':int(left.lane_id),
                                     'exit_road_id':int(exit_wp.road_id),
                                     'requested_heading_change_deg':angle}))
    options.sort(key=lambda item:item[:4])
    if type(candidate_index) is not int or candidate_index<0 or candidate_index>=len(options):
        raise ValueError('No connected marked adjacent-lane left-turn candidate')
    return options[candidate_index][-1]

def targets(selection, case_suffix, *, crossing_fraction=.6):
    if case_suffix not in CASES or not (isfinite(crossing_fraction) and 0<crossing_fraction<1):
        raise ValueError('Invalid selected turn case or crossing request')
    base,adjacent=selection['approach'],selection['adjacent']
    if len(base)!=len(adjacent) or len(base)<5:raise ValueError('Missing matched approach')
    out=[]
    for i,(a,b) in enumerate(zip(base,adjacent)):
        fraction=(crossing_fraction if i>=len(base)//2 and
                  case_suffix!='left_turn_lane_contained_approach' else 0.)
        x,y=_xy(a);u,v=_xy(b);out.append([x+fraction*(u-x),y+fraction*(v-y)])
    out.extend([list(_xy(selection['junction'])),list(_xy(selection['exit']))])
    return {'targets_xy_m':out,'indicator_requested':case_suffix.endswith('_signaled'),
            'engineering_crossing_fraction':0. if case_suffix=='left_turn_lane_contained_approach'
            else crossing_fraction,'requested_turn_heading_deg':selection['requested_heading_change_deg']}
