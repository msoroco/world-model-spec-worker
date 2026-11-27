"""Bundled original CARLA vehicle route controller and readback."""
from __future__ import annotations

import math


def _target_yaw(dx: float, dy: float) -> float:
    return math.degrees(math.atan2(dy, dx))


def configure(world, carla, packet: dict, speed_mps: float):
    itinerary=packet['itinerary']
    points=itinerary['waypoints_xy_m']
    spawn=itinerary['spawn_xyz_m']
    if len(spawn)!=3 or not all(math.isfinite(float(value)) for value in spawn):
        raise ValueError('Original vehicle spawn missing')
    dx=points[1][0]-points[0][0];dy=points[1][1]-points[0][1]
    blueprint=world.get_blueprint_library().find(itinerary['vehicle_blueprint'])
    if blueprint is None or not blueprint.id.startswith('vehicle.'):
        raise ValueError('Original motor vehicle blueprint missing')
    pose=carla.Transform(carla.Location(x=float(spawn[0]),y=float(spawn[1]),z=float(spawn[2])),carla.Rotation(yaw=_target_y(dx,dy)))
    vehicle=world.try_spawn_actor(blueprint,pose)
    if vehicle is None or not vehicle.type_id.startswith('vehicle.'):
        raise RuntimeError('Original motor vehicle spawn failed')
    vehicle.set_autopilot(False)
    return {'vehicle':vehicle,'points':points,'next_index':1,'speed_mps':float(speed_mps)}


def step(handle, carla):
    vehicle=handle['vehicle'];points=handle['points'];index=handle['next_index']
    location=vehicle.get_transform().location
    while index<len(points)-1 and math.hypot(points[index][0]-location.x,points[index][1]-location.y)<3.0:
        index+=1
    handle['next_index']=index
    target=points[index]
    desired=_target_y(target[0]-location.x,target[1]-location.y)
    yaw=vehicle.get_transform().rotation.yaw
    error=(desired-yaw+180.0)%360.0-180.0
    speed=vehicle.get_velocity();speed_now=math.sqrt(speed.x**2+speed.y**2+speed.z**2)
    throttle=max(0.0,min(.55,.24*(handle['speed_mps']-speed_now)))
    brake=0.0 if speed_now<=handle['speed_mps'] else min(.5,.18*(speed_now-handle['speed_mps']))
    vehicle.apply_control(carla.VehicleControl(throttle=throttle,steer=max(-.8,min(.8,error/45.0)),brake=brake))


def sample(world, handle, packet: dict, frame: int, time_s: float) -> dict:
    vehicle=handle['vehicle']
    if not vehicle.is_alive:
        raise RuntimeError('Original ego vehicle no longer alive')
    transform=vehicle.get_transform();position=transform.location
    waypoint=world.get_map().get_waypoint(position,project_to_road=False)
    if waypoint is None:
        raise ValueError('Original vehicle is outside reviewed roadway')
    road_id=int(waypoint.road_id)
    routes=packet['site']['truck_routes'];street=packet['site']['intervening_street']
    if road_id==int(street['road_id']):designation=street['designation']
    elif road_id in (int(routes['origin']['road_id']),int(routes['destination']['road_id'])):designation='truck_route'
    else:raise ValueError('Original vehicle reached unreviewed road identity')
    return {'frame':int(frame),'time_s':float(time_s),'ego_actor_id':int(vehicle.id),
        'position_xy_m':[float(position.x),float(position.y)],'road_id':road_id,
        'street_designation':designation,'activity_kind':None,'observation_source':'original_native_snapshot'}


def teardown(handle):
    vehicle=handle['vehicle']
    if vehicle.is_alive:vehicle.destroy()
