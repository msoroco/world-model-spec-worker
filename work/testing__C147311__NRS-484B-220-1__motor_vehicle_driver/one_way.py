"""Native one-way physical-sign inventory and route-direction binding.

Gate on an actual rendered native sign and same-direction lane topology. The
external designation/authority remains unconfirmed, never inferred from topology.
"""
import math

def native_binding(world,branch):
    mapping=world.get_map()
    signs=[actor for actor in world.get_actors() if 'one_way' in actor.type_id.lower() or 'oneway' in actor.type_id.lower()]
    if not signs:raise RuntimeError('Native map lacks identifiable physical one-way sign actor; no synthetic sign substitution')
    for sign in signs:
        waypoint=mapping.get_waypoint(sign.get_location())
        if waypoint is None:continue
        neighbor=waypoint.get_left_lane() or waypoint.get_right_lane()
        if neighbor is None or neighbor.road_id!=waypoint.road_id or neighbor.lane_id*waypoint.lane_id<=0:continue
        points=[waypoint];current=waypoint
        for _ in range(80):
            next_points=current.next(2.)
            if len(next_points)!=1:break
            current=next_points[0]
            if current.is_junction:break
            points.append(current)
        if len(points)<30:continue
        route=[(p.transform.location.x,p.transform.location.y) for p in points]
        transform=points[0].transform
        if branch=='opposite_direction':
            route.reverse();transform=points[-1].transform
            yaw=(transform.rotation.yaw+180)%360
        else:yaw=transform.rotation.yaw
        return {'map':mapping.name,'blueprint':'vehicle.tesla.model3','spawn':{'location':{'x':transform.location.x,'y':transform.location.y,'z':transform.location.z+.5},'rotation':{'yaw':yaw}},'route':route,'sign_actor_id':sign.id,'sign_transform':str(sign.get_transform()),'authority_status':'unconfirmed','governed_scope_status':'requires independent sign-orientation/native-lane review'}
    raise RuntimeError('Physical one-way sign found but no continuous >=60m multilane same-direction route; retain inventory gap')

def signed_motion(velocity,designated_heading_deg):
    angle=math.radians(designated_heading_deg)
    return velocity[0]*math.cos(angle)+velocity[1]*math.sin(angle)
