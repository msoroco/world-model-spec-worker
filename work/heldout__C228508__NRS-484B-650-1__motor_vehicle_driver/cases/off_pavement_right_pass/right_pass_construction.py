"""Right-side overtaking request beyond mapped driving-lane edge.

Pavement material and any statutory violation require original Native pixels and
independent review; OpenDRIVE lane geometry alone does not establish them.
"""
from math import cos,pi,sin

def rightmost_driving(waypoint):
    current=waypoint;seen=set()
    while True:
        key=(int(current.road_id),int(current.lane_id))
        if key in seen:raise ValueError('Right-lane topology loops')
        seen.add(key)
        neighbor=current.get_right_lane()
        if (neighbor is None or 'driving' not in str(neighbor.lane_type).lower() or
                int(neighbor.road_id)!=int(current.road_id)):
            return current
        current=neighbor

def right_edge_target(waypoint,extra_m=1.5):
    if extra_m not in (1.5,2.5):raise ValueError('Unsupported off-road excursion')
    edge_lane=rightmost_driving(waypoint)
    angle=edge_lane.transform.rotation.yaw*pi/180
    right=(sin(angle),-cos(angle))
    center=edge_lane.transform.location
    half=float(edge_lane.lane_width)/2
    if half<=0:raise ValueError('Invalid mapped right lane width')
    edge=(center.x+half*right[0],center.y+half*right[1])
    target=(edge[0]+extra_m*right[0],edge[1]+extra_m*right[1])
    return {'road_edge_xy_m':edge,'target_xy_m':target,
            'rightmost_lane_id':int(edge_lane.lane_id),'rightmost_road_id':int(edge_lane.road_id),
            'lateral_right':right}

def pass_target(route,station_m,route_index,extra_m=1.5):
    waypoint=route[min(route_index+3,len(route)-1)]
    if not 300<=station_m<550:
        point=waypoint.transform.location
        return (point.x,point.y)
    return right_edge_target(waypoint,extra_m)['target_xy_m']
