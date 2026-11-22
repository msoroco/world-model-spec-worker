"""Lazy Native actor lifecycle and route controls for the yield-sign case."""
from contextlib import contextmanager
import math

from median_yield_route import validate_scene, yield_control
from yield_sign_control import find_governing_yield_sign


def _speed(actor):
    velocity=actor.get_velocity()
    value=math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
    if not math.isfinite(value):
        raise ValueError('Nonfinite Native speed')
    return value


def _steer(actor, route, target_index):
    pose=actor.get_transform()
    point=pose.location
    if not 1<=target_index<len(route):
        raise ValueError('Invalid route index')
    while target_index<len(route)-1 and math.dist(
            (point.x,point.y),route[target_index])<4:
        target_index+=1
    target=route[target_index]
    bearing=math.atan2(target[1]-point.y,target[0]-point.x)
    error=(bearing-math.radians(pose.rotation.yaw)+math.pi)%(2*math.pi)-math.pi
    distance=max(4,math.dist((point.x,point.y),target))
    curvature=2*math.sin(error)/distance
    return max(-1,min(1,-math.atan(2.8*curvature)/math.radians(35))),target_index


def _line_distance(actor,scene):
    pose=actor.get_transform()
    start=scene['approaches']['ego']['route_xy_m'][0]
    line=scene['ego_yield_line_xy_m']
    dx,dy=line[0]-start[0],line[1]-start[1]
    length=math.hypot(dx,dy)
    if length<1:
        raise ValueError('Yield line and route start must be separated')
    return ((line[0]-pose.location.x)*dx+(line[1]-pose.location.y)*dy)/length


@contextmanager
def construct_pair(world,scene,ego_blueprint,other_blueprint,
                   ego_transform,other_transform,ego_entrance_waypoint):
    """Verify the entrance's Native yield sign and own both spawned vehicles."""
    validate_scene(scene)
    sign=find_governing_yield_sign(world,ego_entrance_waypoint)
    if sign.id!=scene['yield_sign']['native_id']:
        raise ValueError('Governing Native yield sign ID differs from reviewed scene')
    owned=[]
    try:
        for blueprint,transform,role in (
                (ego_blueprint,ego_transform,'ego'),
                (other_blueprint,other_transform,'other')):
            actor=world.try_spawn_actor(blueprint,transform)
            if actor is None:
                raise ValueError(role+' Native spawn failed')
            owned.append(actor)
        yield owned[0],owned[1],sign
    finally:
        for actor in reversed(owned):
            actor.destroy()


def step_pair(carla,ego,other,scene,progress,conflict_clear,other_release,
              ego_target_mps=5.0,other_target_mps=5.0):
    """Apply one route-control step from observed conflict state."""
    validate_scene(scene)
    if type(conflict_clear) is not bool or type(other_release) is not bool:
        raise ValueError('Measured conflict and release booleans required')
    next_progress={}
    commands={}
    for role,actor,target in (('ego',ego,ego_target_mps),
                              ('other',other,other_target_mps)):
        steer,next_progress[role]=_steer(actor,scene['approaches'][role]['route_xy_m'],
                                         progress[role])
        speed=_speed(actor)
        if role=='ego':
            throttle,brake=yield_control(_line_distance(actor,scene),speed,
                                         conflict_clear,target)
        elif not other_release:
            throttle,brake=0.0,1.0
        else:
            throttle=min(.5,max(0.0,(target-speed)*.18))
            brake=min(.5,max(0.0,(speed-target)*.2))
        command=carla.VehicleControl()
        command.steer,command.throttle,command.brake=steer,throttle,brake
        actor.apply_control(command)
        commands[role]={'steer':steer,'throttle':throttle,'brake':brake,
                        'speed_mps':speed}
    return next_progress,commands
