"""Visible passenger activity request for the standing branch.

Walking toward and away from the vehicle is an authored action, not proof that
passengers were actually loaded or unloaded or that a legal definition applies.
"""
from __future__ import annotations

import math

WALKER_START = (7.8, -6.0, .5)
VEHICLE_SIDE = (5.6, 0.0, .5)


def spawn(config, world, carla):
    if config['activity_requested'] == 'parking':
        return None
    if config['activity_requested'] != 'standing':
        raise ValueError('Unknown exact activity branch')
    blueprint = world.get_blueprint_library().find('walker.pedestrian.0001')
    blueprint.set_attribute('role_name', 'c229351_passenger')
    passenger = world.spawn_actor(blueprint, carla.Transform(
        carla.Location(x=WALKER_START[0], y=WALKER_START[1], z=WALKER_START[2])))
    if passenger is None:
        raise RuntimeError('Original passenger actor failed to spawn')
    return passenger


def control(passenger, elapsed_s, carla):
    if passenger is None:
        return 'no_passenger_request'
    if elapsed_s < 8:
        target, speed, phase = VEHICLE_SIDE, 1.0, 'approach_vehicle'
    elif elapsed_s < 13:
        target, speed, phase = VEHICLE_SIDE, 0.0, 'at_vehicle_side'
    elif elapsed_s < 21:
        target, speed, phase = WALKER_START, 1.0, 'depart_vehicle'
    else:
        target, speed, phase = WALKER_START, 0.0, 'observation'
    position = passenger.get_location()
    dx, dy = target[0] - position.x, target[1] - position.y
    norm = math.hypot(dx, dy)
    if norm < .25 or speed == 0:
        direction, speed = carla.Vector3D(0, 0, 0), 0.0
    else:
        direction = carla.Vector3D(dx / norm, dy / norm, 0)
    passenger.apply_control(carla.WalkerControl(direction=direction, speed=speed))
    return phase
