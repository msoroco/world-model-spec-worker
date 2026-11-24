"""Read one complete original CARLA traffic-control actor inventory."""
from __future__ import annotations

import math


def vector(value):
    result = [value.x, value.y, value.z]
    if any(type(item) not in (int, float) or not math.isfinite(item)
           for item in result):
        raise ValueError('original Native traffic-control vector invalid')
    return [float(item) for item in result]


def observe(world, frame: int, time_s: float) -> dict:
    if (type(frame) is not int or frame < 0 or
            type(time_s) not in (int, float) or not math.isfinite(time_s)):
        raise ValueError('original Native traffic-control clock invalid')
    actors = list(world.get_actors())
    controls = [actor for actor in actors
                if isinstance(getattr(actor, 'type_id', None), str)
                and actor.type_id.startswith('traffic.')
                and getattr(actor, 'is_alive', True)]
    ids = [actor.id for actor in controls]
    if (any(type(ident) is not int or ident < 0 for ident in ids) or
            len(ids) != len(set(ids))):
        raise ValueError('original Native traffic-control identities invalid')
    devices = []
    for actor in sorted(controls, key=lambda item: item.id):
        record = {'actor_id': actor.id, 'blueprint': actor.type_id,
                  'position_m': vector(actor.get_transform().location)}
        if actor.type_id == 'traffic.traffic_light':
            boxes = list(actor.get_light_boxes())
            if not boxes:
                raise ValueError('original Native signal light boxes missing')
            record['light_box_method'] = 'TrafficLight.get_light_boxes'
            record['light_boxes'] = [
                {'light_box_index': index,
                 'location_m': vector(box.location),
                 'extent_m': vector(box.extent)}
                for index, box in enumerate(boxes)]
            record['state'] = str(actor.get_state()).split('.')[-1]
        devices.append(record)
    return {'frame': frame, 'time_s': time_s, 'devices': devices,
            'control_actor_inventory': {
                'frame': frame, 'time_s': time_s,
                'method': 'World.get_actors', 'prefix': 'traffic.',
                'actor_ids': sorted(ids), 'complete': True}}
