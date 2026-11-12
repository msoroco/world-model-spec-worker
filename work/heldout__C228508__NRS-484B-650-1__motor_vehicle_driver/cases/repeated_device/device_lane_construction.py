"""Map-linked signal and marked-lane route for C228508 candidate acts.

Official authority, traffic-control violation and unsafe lane use remain
unresolved until original Native sources and governing law are reviewed.
"""
from math import atan2, cos, hypot, pi, sin


def _xy(waypoint):
    p = waypoint.transform.location
    return float(p.x), float(p.y)


def _driving(waypoint):
    return waypoint is not None and 'driving' in str(waypoint.lane_type).lower()


def _heading(waypoint):
    r = waypoint.transform.rotation.yaw * pi / 180
    return cos(r), sin(r)


def _next_through(waypoint, step_m=5):
    forward = _heading(waypoint)
    candidates = []
    for next_waypoint in waypoint.next(step_m):
        if not _driving(next_waypoint):
            continue
        aligned = sum(a*b for a,b in zip(forward, _heading(next_waypoint)))
        if aligned > .75:
            candidates.append((aligned, next_waypoint))
    if not candidates:
        raise ValueError('No through driving-lane continuation')
    candidates.sort(key=lambda x:x[0], reverse=True)
    if len(candidates)>1 and candidates[0][0]-candidates[1][0]<.01:
        raise ValueError('Ambiguous through driving-lane continuation')
    return candidates[0][1]


def _marked_neighbor(waypoint):
    marking = waypoint.left_lane_marking
    if marking is None or str(marking.type).rsplit('.',1)[-1].lower()=='none':
        raise ValueError('Selected lane has no original marked left boundary')
    neighbor = waypoint.get_left_lane()
    if not _driving(neighbor) or int(neighbor.road_id)!=int(waypoint.road_id):
        raise ValueError('No adjacent marked driving lane')
    return neighbor


def _route(affected, *, before_m=150, length_m=2200, step_m=5):
    starts = affected.previous(before_m)
    if len(starts)!=1 or not _driving(starts[0]):
        raise ValueError('No unique signal approach start')
    route=[starts[0]];distance=[0.0]
    while distance[-1]<length_m:
        nxt=_next_through(route[-1],step_m)
        a,b=_xy(route[-1]),_xy(nxt)
        segment=hypot(b[0]-a[0],b[1]-a[1])
        if segment<step_m*.25 or segment>step_m*2:
            raise ValueError('Signal route discontinuity')
        route.append(nxt);distance.append(distance[-1]+segment)
        if len(route)>10000:raise ValueError('Signal route did not terminate')
    stop=min(range(len(route)),key=lambda i:hypot(*[a-b for a,b in zip(_xy(route[i]),_xy(affected))]))
    if not 100<=distance[stop]<=250:
        raise ValueError('Selected signal does not govern approach segment')
    lane_index=min(range(len(distance)),key=lambda i:abs(distance[i]-700))
    neighbor=_marked_neighbor(route[lane_index])
    return {'route':route,'distance_m':distance,'stop_station_m':distance[stop],
            'marked_lane_station_m':distance[lane_index],
            'marked_lane_id':int(route[lane_index].lane_id),
            'adjacent_lane_id':int(neighbor.lane_id)}


def select_site(world_map, lights, *, candidate_index=0, before_m=150):
    if type(candidate_index) is not int or candidate_index<0:
        raise ValueError('Invalid site candidate index')
    candidates=[]
    for light in lights:
        if not hasattr(light,'get_affected_lane_waypoints') or not hasattr(light,'set_state'):
            continue
        for affected in light.get_affected_lane_waypoints():
            try:
                site=_route(affected,before_m=before_m)
            except ValueError:
                continue
            site.update(light=light,affected=affected,
                        light_actor_id=int(light.id),
                        opendrive_id=str(light.get_opendrive_id()))
            if not site['opendrive_id']:
                continue
            candidates.append(site)
    candidates.sort(key=lambda s:(s['light_actor_id'],int(s['affected'].road_id),
                                  int(s['affected'].lane_id)))
    if candidate_index>=len(candidates):
        raise ValueError('No requested signal/marked-lane site')
    return candidates[candidate_index]


def lane_target(site, station_m, route_index, fraction=.6):
    if not 0<fraction<1:raise ValueError('Invalid physical lane excursion fraction')
    base=site['route'][min(route_index+3,len(site['route'])-1)]
    if not 700<=station_m<900:
        return _xy(base)
    neighbor=_marked_neighbor(base)
    x,y=_xy(base);nx,ny=_xy(neighbor)
    return x+fraction*(nx-x),y+fraction*(ny-y)


def select_pair(world_map, lights, *, candidate_index=0):
    """Select two distinct OpenDRIVE-linked lights on one through route."""
    light_list=list(lights)
    first=select_site(world_map,light_list,candidate_index=candidate_index)
    route,distance=first['route'],first['distance_m']
    second=[]
    for light in light_list:
        if int(light.id)==first['light_actor_id'] or not hasattr(light,'get_affected_lane_waypoints'):
            continue
        opendrive_id=str(light.get_opendrive_id())
        if not opendrive_id:continue
        for affected in light.get_affected_lane_waypoints():
            if not _driving(affected):continue
            nearest=min(range(len(route)),key=lambda i:hypot(*[a-b for a,b in zip(_xy(route[i]),_xy(affected))]))
            if not 450<=distance[nearest]<=1200:continue
            if hypot(*[a-b for a,b in zip(_xy(route[nearest]),_xy(affected))])>4:continue
            if (int(route[nearest].road_id),int(route[nearest].lane_id))!=(int(affected.road_id),int(affected.lane_id)):
                continue
            second.append({'light':light,'light_actor_id':int(light.id),'opendrive_id':opendrive_id,
                           'stop_station_m':distance[nearest]})
    second.sort(key=lambda s:(s['stop_station_m'],s['light_actor_id']))
    if not second:raise ValueError('No second distinct governed signal on route')
    return first,second[0]
