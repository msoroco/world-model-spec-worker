"""Select a connected narrow two-direction Native route before spawning."""
from math import hypot


def _xy(waypoint):
    p=waypoint.transform.location
    return float(p.x),float(p.y)


def _opposing(waypoint):
    for candidate in (waypoint.get_left_lane(),waypoint.get_right_lane()):
        if (candidate is not None and candidate.road_id==waypoint.road_id
                and candidate.lane_id*waypoint.lane_id<0
                and not candidate.is_junction
                and abs(candidate.lane_width-waypoint.lane_width)<=.75):
            return candidate
    raise ValueError('opposite-direction adjacent lane absent')


def route_from(start,step_m=5.0):
    if step_m<=0:raise ValueError('invalid Native sampling step')
    if start.is_junction or not 2.3<=start.lane_width<=3.5:
        raise ValueError('narrow nonjunction lane required')
    chain=[start]
    for _ in range(32):
        choices=[w for w in chain[-1].next(step_m)
                 if w.road_id==start.road_id and w.lane_id==start.lane_id and not w.is_junction]
        if len(choices)!=1:raise ValueError('narrow route is not uniquely connected')
        nxt=choices[0]
        distance=hypot(nxt.transform.location.x-chain[-1].transform.location.x,
                       nxt.transform.location.y-chain[-1].transform.location.y)
        if not .5*step_m<=distance<=1.6*step_m:
            raise ValueError('narrow route has discontinuous sample')
        chain.append(nxt)
    opposite=_opposing(chain[24])
    if hypot(*[a-b for a,b in zip(_xy(opposite),_xy(chain[24]))])>2*start.lane_width+1:
        raise ValueError('opposing lane is not adjacent')
    return {'ego':chain[8],'follower':chain[4],'opposing':opposite,
            'obstruction_site':chain[12], 'chain':chain,
            'road_id':start.road_id,'ego_lane_id':start.lane_id,
            'opposing_lane_id':opposite.lane_id,
            'lane_width_m':start.lane_width}


def select_route(world_map,step_m=5.0):
    errors=[]
    for spawn in world_map.get_spawn_points():
        start=world_map.get_waypoint(spawn.location)
        if start is None:continue
        try:return route_from(start,step_m)
        except ValueError as error:errors.append(str(error))
    raise ValueError('No connected narrow two-direction Native route: '+'; '.join(sorted(set(errors))))
