"""Native hill-crest route and two-vehicle spawn for C101303.

Road IDs and hill classification must be source reviewed. Crest geometry and
adjacent driving lane are checked from actual Native waypoints before capture.
"""
from contextlib import contextmanager
import math


def _point(waypoint):
    p=waypoint.transform.location
    xyz=(float(p.x),float(p.y),float(p.z))
    if not all(math.isfinite(v) for v in xyz):raise ValueError('Nonfinite Native waypoint')
    return xyz

def _distance(a,b):
    return math.dist(_point(a),_point(b))

def select_hill_crest_route(native_map,start_transform,*,reviewed_road_id,
                            following_lane_id,target_lane_id,step_m=3.0,
                            minimum_length_m=30.0,minimum_crest_rise_m=0.5):
    if type(reviewed_road_id) is not int or type(following_lane_id) is not int or type(target_lane_id) is not int:
        raise ValueError('Source-reviewed Native road and lane IDs required')
    if target_lane_id==following_lane_id or step_m<=0 or minimum_length_m<=0 or minimum_crest_rise_m<=0:
        raise ValueError('Valid route geometry parameters required')
    start=native_map.get_waypoint(start_transform.location,project_to_road=False)
    if start is None or start.road_id!=reviewed_road_id or start.lane_id!=following_lane_id or start.is_junction:
        raise ValueError('Start is not in sourced following lane')
    path=[start];length=0.0
    for _ in range(math.ceil(minimum_length_m/step_m)+20):
        choices=[w for w in path[-1].next(step_m) if w.road_id==reviewed_road_id
                 and w.lane_id==following_lane_id and not w.is_junction
                 and str(w.lane_type).lower().endswith('driving')]
        if len(choices)!=1:break
        next_wp=choices[0];segment=_distance(path[-1],next_wp)
        if segment<=0 or not math.isfinite(segment):break
        length+=segment;path.append(next_wp)
        if length>=minimum_length_m:break
    if length<minimum_length_m:raise ValueError('Native following corridor too short')
    elevations=[_point(w)[2] for w in path]
    crest=max(range(1,len(path)-1),key=lambda i:elevations[i],default=None)
    if crest is None or elevations[crest]-max(elevations[0],elevations[-1])<minimum_crest_rise_m:
        raise ValueError('No measured Native hill crest')
    adjacent=[]
    for candidate in (path[crest].get_left_lane(),path[crest].get_right_lane()):
        if candidate is not None and candidate.road_id==reviewed_road_id and candidate.lane_id==target_lane_id and str(candidate.lane_type).lower().endswith('driving'):
            adjacent.append(candidate)
    if len(adjacent)!=1:raise ValueError('Selected adjacent driving lane missing at crest')
    return {'waypoints':path,'target_lane_waypoint':adjacent[0],
            'crest_waypoint_index':crest,'crest_rise_m':elevations[crest]-max(elevations[0],elevations[-1]),
            'corridor_length_m':length,'road_id':reviewed_road_id,
            'following_lane_id':following_lane_id,'target_lane_id':target_lane_id}

@contextmanager
def spawn_following_pair(world,blueprint,ego_transform,lead_transform,
                         *,minimum_initial_separation_m=4.0):
    owned=[]
    try:
        lead=world.try_spawn_actor(blueprint,lead_transform)
        if lead is None:raise ValueError('Native lead vehicle spawn failed')
        owned.append(lead)
        ego=world.try_spawn_actor(blueprint,ego_transform)
        if ego is None:raise ValueError('Native ego vehicle spawn failed')
        owned.append(ego)
        a,b=ego.get_location(),lead.get_location()
        separation=math.dist((a.x,a.y,a.z),(b.x,b.y,b.z))
        if separation<minimum_initial_separation_m:
            raise ValueError('Initial vehicle positions overlap')
        yield {'ego':ego,'lead':lead,'initial_center_separation_m':separation}
    finally:
        for actor in reversed(owned):actor.destroy()


def discover_hill_crest_route(native_map,*,minimum_length_m=30.0,step_m=3.0,minimum_crest_rise_m=0.5):
    """Search Native driving waypoints; return measured candidate for source review."""
    candidates=[]
    for start in native_map.generate_waypoints(step_m):
        if start.is_junction or not str(start.lane_type).lower().endswith('driving'):
            continue
        for adjacent in (start.get_left_lane(),start.get_right_lane()):
            if adjacent is None or adjacent.road_id!=start.road_id or adjacent.lane_id==start.lane_id:
                continue
            if not str(adjacent.lane_type).lower().endswith('driving'):
                continue
            try:
                candidate=select_hill_crest_route(native_map,start.transform,
                    reviewed_road_id=start.road_id,following_lane_id=start.lane_id,
                    target_lane_id=adjacent.lane_id,step_m=step_m,
                    minimum_length_m=minimum_length_m,minimum_crest_rise_m=minimum_crest_rise_m)
                candidates.append(candidate)
            except ValueError:
                continue
    if not candidates:raise ValueError('No measured Native hill-crest lane-change route')
    selected=max(candidates,key=lambda row:(row['crest_rise_m'],row['corridor_length_m']))
    selected['source_review_status']='native_geometry_candidate; legal highway and scenario eligibility unresolved'
    return selected
