"""Prospective right-half closure objects and original Native readback.

Cones make a physical obstacle candidate; they do not establish an authorized
traffic closure or a legal exception.
"""

import json
from math import hypot
from pathlib import Path


def closure_transforms(carla, waypoint, *, fractions=(-0.35, 0.0, 0.35)):
    width = float(waypoint.lane_width)
    if width <= 0:
        raise ValueError('Closure lane width unavailable')
    vector = waypoint.transform.get_forward_vector()
    norm = hypot(vector.x, vector.y)
    if norm < .8:
        raise ValueError('Closure route tangent unavailable')
    right_x, right_y = -vector.y / norm, vector.x / norm
    location = waypoint.transform.location
    if len(fractions) < 3 or len(set(fractions)) != len(fractions) or any(
            not -0.5 < value < 0.5 for value in fractions):
        raise ValueError('Closure must span three distinct lane-interior points')
    return [carla.Transform(carla.Location(
        x=location.x + right_x * width * value,
        y=location.y + right_y * width * value,
        z=location.z + 0.05), waypoint.transform.rotation)
            for value in fractions]


def spawn_closure(world, carla, waypoint):
    blueprints = list(world.get_blueprint_library().filter('static.prop.trafficcone*'))
    if not blueprints:
        raise ValueError('No Native traffic-cone blueprint available')
    blueprint = blueprints[0]
    actors = []
    try:
        for transform in closure_transforms(carla, waypoint):
            actor = world.try_spawn_actor(blueprint, transform)
            if actor is None:
                raise ValueError('Native right-half closure cone spawn failed')
            actors.append(actor)
        return actors
    except Exception:
        for actor in reversed(actors):
            actor.destroy()
        raise


class ClosureSourceRecorder:
    def __init__(self, output, actors):
        if len(actors) < 3 or len({a.id for a in actors}) != len(actors):
            raise ValueError('Closure requires three distinct original actors')
        self.actors = actors
        self.path = Path(output) / 'closure_devices.jsonl'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open('x', encoding='utf-8')
        self.previous = None

    def append(self, frame, time_s):
        if self.previous is not None:
            old_frame, old_time = self.previous
            if frame != old_frame + 1 or abs(time_s - old_time - .05) > 1e-4:
                raise ValueError('Closure original source not continuous at 20 Hz')
        devices = []
        for actor in self.actors:
            transform = actor.get_transform()
            point = transform.location
            devices.append({'actor_id': str(actor.id),
                            'blueprint_id': actor.type_id,
                            'position_m': [float(point.x), float(point.y),
                                           float(point.z)]})
        if len({d['actor_id'] for d in devices}) != len(devices):
            raise ValueError('Closure original actor IDs changed')
        row = {'frame': int(frame), 'time_s': float(time_s),
               'devices': devices, 'authority_verified': False}
        self.file.write(json.dumps(row, sort_keys=True) + '\n')
        self.file.flush()
        self.previous = frame, time_s
        return row

    def close(self):
        self.file.close()
