"""Bounded two-actor waypoint control for prospective Native left turns.

Controls are engineering commands. Crossing order and simultaneous physical
turns must be measured from original actor sources after capture.
"""

import math


def next_target(actor, path, index, *, proximity_m=2.0):
    if len(path) < 3 or not 0 <= index < len(path):
        raise ValueError('connected turn path and current index required')
    location = actor.get_location()
    while index + 1 < len(path) and location.distance(path[index].transform.location) < proximity_m:
        index += 1
    return index, path[index].transform.location


def bounded_control(actor, target, *, target_speed_mps=5.0, throttle_gain=0.12):
    if not 0 < target_speed_mps <= 12 or not 0 < throttle_gain <= 0.5:
        raise ValueError('unsupported turn controller bounds')
    pose = actor.get_transform()
    current = math.radians(float(pose.rotation.yaw))
    desired = math.atan2(target.y - pose.location.y, target.x - pose.location.x)
    error = math.atan2(math.sin(desired-current), math.cos(desired-current))
    velocity = actor.get_velocity()
    speed = math.hypot(velocity.x, velocity.y)
    delta = target_speed_mps - speed
    throttle = min(0.45, max(0.0, delta * throttle_gain))
    brake = min(0.5, max(0.0, -delta * throttle_gain))
    steer = max(-0.75, min(0.75, error / math.radians(45)))
    return {'throttle': throttle, 'brake': brake, 'steer': steer}


def command_pair(actors, paths, indices, tick, *, start_delays=(0, 0),
                 target_speeds=(5.0, 5.0), throttle_gain=0.12):
    if len(actors) != 2 or len(paths) != 2 or len(indices) != 2:
        raise ValueError('two Native actors and routes required')
    if len(start_delays) != 2 or any(type(delay) is not int or not 0 <= delay <= 3 for delay in start_delays):
        raise ValueError('unsupported simultaneous-turn start delay')
    commands = []
    updated = []
    for actor, path, index, delay, speed in zip(actors, paths, indices, start_delays, target_speeds):
        index, target = next_target(actor, path, index)
        updated.append(index)
        commands.append(({'throttle': 0.0, 'brake': 1.0, 'steer': 0.0}
                         if tick < delay else bounded_control(actor, target,
                                      target_speed_mps=speed, throttle_gain=throttle_gain)))
    return updated, commands
