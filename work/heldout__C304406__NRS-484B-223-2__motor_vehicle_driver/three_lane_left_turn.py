"""Find a connected left-turn exit from a marked three-lane center approach.

This is map geometry, not proof that a left turn was physically completed.
"""

from math import atan2, degrees, hypot
from three_lane_route import ordered_lanes, _unit


def signed_turn_deg(start_xy, end_xy):
    a, b = start_xy, end_xy
    return degrees(atan2(a[0]*b[1]-a[1]*b[0], a[0]*b[0]+a[1]*b[1]))


def select_left_turn_connection(right_route, *, spacing_m=2.5, max_depth=20):
    """Breadth-search a center-lane junction branch with a leftward exit."""
    if len(right_route)<5 or spacing_m<=0 or max_depth<2:
        raise ValueError('Left-turn approach parameters invalid')
    centers=[ordered_lanes(right)['center'] for right in right_route]
    start=centers[-1]
    start_heading=_unit(start)
    queue=[(start,[start],False)]
    seen={(start.road_id,start.lane_id,round(start.transform.location.x,2),
           round(start.transform.location.y,2))}
    for _ in range(max_depth):
        next_queue=[]
        for current,path,entered_junction in queue:
            for successor in current.next(spacing_m):
                if successor is None or 'driving' not in str(getattr(successor,'lane_type','')).lower():
                    continue
                point=successor.transform.location
                identity=(successor.road_id,successor.lane_id,round(point.x,2),round(point.y,2))
                if identity in seen:
                    continue
                seen.add(identity)
                junction=entered_junction or bool(successor.is_junction)
                branch=path+[successor]
                if junction and not successor.is_junction and successor.road_id!=start.road_id:
                    angle=signed_turn_deg(start_heading,_unit(successor))
                    if 45<=angle<=135:
                        return {'approach_center_route':centers,
                                'turn_branch':branch,'left_exit':successor,
                                'turn_angle_deg':angle,
                                'junction_entered':True}
                next_queue.append((successor,branch,junction))
        queue=next_queue
        if not queue:
            break
    raise ValueError('No connected center-lane left-turn junction exit')


def preparation_distance_m(ego_xy, approach_end_xy, travel_xy):
    norm=hypot(*travel_xy)
    if norm<.8:
        raise ValueError('Left-turn approach heading missing')
    return ((approach_end_xy[0]-ego_xy[0])*travel_xy[0]+
            (approach_end_xy[1]-ego_xy[1])*travel_xy[1])/norm
