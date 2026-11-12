"""Choose a cross-highway vehicle already entering a governed junction.

NRS 484B.250(1) priority remains an independent Native and legal review matter.
"""
from math import cos,hypot,pi,sin

def _xy(w):
    p=w.transform.location
    return float(p.x),float(p.y)
def _yaw(w):
    return w.transform.rotation.yaw*pi/180
def _driving(w):
    return w is not None and 'driving' in str(w.lane_type).lower()
def _dist(a,b):
    return hypot(*[x-y for x,y in zip(_xy(a),_xy(b))])
def choose_cross_traffic(site,lights,carla,*,spawn_offset_m=8):
    if spawn_offset_m not in (8,12):raise ValueError('Unsupported cross-traffic spawn offset')
    route,distance=site['route'],site['distance_m']
    approaches=[w for w,d in zip(route,distance) if site['stop_station_m']<=d<=site['stop_station_m']+60 and w.is_junction]
    if not approaches:raise ValueError('Signal route has no traversed junction')
    ego=approaches[0];junction=ego.get_junction()
    if junction is None:raise ValueError('No Native junction geometry')
    forward=(cos(_yaw(ego)),sin(_yaw(ego)))
    candidates=[]
    for entry,exit in junction.get_waypoints(carla.LaneType.Driving):
        if not _driving(entry) or not _driving(exit):continue
        if int(entry.road_id)==int(ego.road_id):continue
        cross=(cos(_yaw(entry)),sin(_yaw(entry)))
        if abs(sum(x*y for x,y in zip(forward,cross)))>.5:continue
        starts=[w for w in entry.previous(spawn_offset_m) if _driving(w)]
        if len(starts)!=1:continue
        for light in lights:
            if int(light.id)==site['light_actor_id'] or not hasattr(light,'get_affected_lane_waypoints'):
                continue
            matched=[w for w in light.get_affected_lane_waypoints() if
                     int(w.road_id)==int(entry.road_id) and int(w.lane_id)==int(entry.lane_id)
                     and _dist(w,entry)<50]
            if not matched:continue
            candidates.append((int(entry.road_id),int(entry.lane_id),int(light.id),
                {'junction_id':int(junction.id),'entry':entry,'exit':exit,'spawn':starts[0],
                 'cross_light':light,'cross_light_actor_id':int(light.id),
                 'cross_opendrive_id':str(light.get_opendrive_id())}))
    candidates.sort(key=lambda x:x[:3])
    if not candidates:raise ValueError('No governed perpendicular cross-highway vehicle lane')
    selected=candidates[0][3]
    if not selected['cross_opendrive_id']:raise ValueError('Cross-traffic signal lacks OpenDRIVE ID')
    return selected

def cross_target(selected,cross_vehicle):
    exit=selected['exit'];x,y=_xy(exit);angle=_yaw(exit)
    return x+100*cos(angle),y+100*sin(angle)
