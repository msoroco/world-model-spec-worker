"""Retain Native control and crossing inventories without legal conclusions."""

import json
from pathlib import Path


def _xyz(point):
    return [float(point.x), float(point.y), float(point.z)]


def observe_controls(world, expected_yield_id, *, frame=None):
    """Sample current actors/map once; a sign face still needs pixel review."""
    if frame is not None and world.get_snapshot().frame != frame:
        raise ValueError('Control inventory frame differs from current world')
    actors = list(world.get_actors())
    yield_signs = [actor for actor in actors if actor.type_id.startswith('traffic.yield')]
    matched = [actor for actor in yield_signs if actor.id == expected_yield_id]
    if len(matched) != 1:
        raise ValueError('Native yield sign disappeared or changed identity')
    sign = matched[0]
    transform = sign.get_transform()
    if not hasattr(sign, 'trigger_volume'):
        raise ValueError('Native yield sign lacks trigger volume')
    trigger = [_xyz(point) for point in
               sign.trigger_volume.get_world_vertices(transform)]
    if len(trigger) < 4:
        raise ValueError('Native yield trigger geometry incomplete')
    crosswalks = [_xyz(point) for point in world.get_map().get_crosswalks()]
    competing = [{'actor_id': actor.id, 'blueprint': actor.type_id,
                  'position_m': _xyz(actor.get_transform().location)}
                 for actor in actors if actor.type_id.startswith(
                     ('traffic.stop', 'traffic.traffic_light'))]
    return {'frame': frame, 'native_map_name': world.get_map().name,
            'yield_sign': {'actor_id': sign.id, 'blueprint': sign.type_id,
                           'position_m': _xyz(transform.location),
                           'trigger_vertices_m': trigger},
            'other_yield_sign_ids': [actor.id for actor in yield_signs if actor.id != sign.id],
            'competing_controls': competing,
            'native_crosswalk_vertices_m': crosswalks,
            'stop_line_decal_absence': 'unverified_from_Native_control_inventory',
            'sign_face_legibility': 'unverified_from_Native_control_inventory',
            'police_direction': 'unverified_from_Native_control_inventory'}


class ControlWriter:
    def __init__(self, root):
        self.path = Path(root) / 'control_inventory.jsonl'
        if self.path.exists():
            raise ValueError('Retain prior Native control inventory')
        self.previous_frame = -1

    def add(self, row):
        frame = row.get('frame')
        if type(frame) is not int or frame <= self.previous_frame:
            raise ValueError('Control inventory frames must increase')
        with self.path.open('a') as stream:
            stream.write(json.dumps(row, sort_keys=True) + '\n')
        self.previous_frame = frame
