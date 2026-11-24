"""Serialize one observed C10301 CARLA world frame as an original adapter graph.

The caller supplies the actor and the snapshot returned by the same world tick.
This module does not infer legal status or physical completion from actor state.
"""

from __future__ import annotations

import json
import math


def _vector(value):
    coordinates = [value.x, value.y, value.z]
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in coordinates):
        raise ValueError('CARLA actor vector is not finite')
    return coordinates


def _actor_node(actor, *, ego):
    transform = actor.get_transform()
    box = actor.bounding_box
    velocity = actor.get_velocity()
    forward = transform.get_forward_vector()
    vertices = box.get_world_vertices(transform)
    if len(vertices) != 8:
        raise ValueError('CARLA graph original full body vertices missing')
    attributes = {
        'source_actor_id': actor.id,
        'type_id': actor.type_id,
        'carla_id': actor.id,
        'sem_class': actor.type_id,
        'vertex': _vector(transform.location),
        'forward': _vector(forward),
        'threedbbox': [_vector(vertex) for vertex in vertices],
        'original_observation': {'velocity_mps': _vector(velocity)},
        'location_m': _vector(transform.location),
        'rotation_deg': [transform.rotation.pitch, transform.rotation.yaw,
                         transform.rotation.roll],
        'velocity_mps': _vector(velocity),
        'bounding_box_location_m': _vector(box.location),
        'bounding_box_extent_m': _vector(box.extent),
    }
    if ego:
        attributes['actor_id'] = actor.id
    if (type(actor.id) is not int or actor.id <= 0 or
            not isinstance(actor.type_id, str) or not actor.type_id or
            any(type(v) not in (int, float) or not math.isfinite(v)
                for v in attributes['rotation_deg'])):
        raise ValueError('CARLA actor identity or rotation invalid')
    return {'id': 'ego' if ego else f'actor:{actor.id}', 'attributes': attributes}


def collect(world, ego_actor, snapshot, *, expected_frame: int,
            expected_time_s: float, recording_time_s: float,
            observed_evidence=None) -> bytes:
    """Read live actors only after an exact-frame world snapshot is available."""
    if (type(expected_frame) is not int or expected_frame < 0 or
            type(expected_time_s) not in (int, float) or
            not math.isfinite(expected_time_s)):
        raise ValueError('expected graph frame/time invalid')
    if (snapshot.frame != expected_frame or
            abs(snapshot.timestamp.elapsed_seconds - expected_time_s) > .001):
        raise ValueError('CARLA graph snapshot frame/time differs')
    actors = list(world.get_actors())
    matches = [actor for actor in actors if actor.id == ego_actor.id]
    if len(matches) != 1 or not getattr(matches[0], 'is_alive', False):
        raise ValueError('CARLA graph ego actor absent')
    # Camera sensors are CARLA actors too. They are capture instruments, not
    # road participants, and their bounding boxes are not a traffic source.
    others = sorted((actor for actor in actors if actor.id != ego_actor.id
                     and getattr(actor, 'is_alive', False)
                     and isinstance(getattr(actor, 'type_id', None), str)
                     and actor.type_id.startswith(('vehicle.', 'walker.'))),
                    key=lambda actor: actor.id)
    ids = [actor.id for actor in others]
    if len(ids) != len(set(ids)):
        raise ValueError('CARLA graph actor IDs duplicated')
    if (type(recording_time_s) not in (int, float) or
            not math.isfinite(recording_time_s) or recording_time_s < 0):
        raise ValueError('original graph recording clock invalid')
    metadata = {'frame': expected_frame,
                'simulation_time_s': recording_time_s,
                'source': 'live_carla_world_snapshot'}
    signal_nodes = []
    if observed_evidence is not None:
        if (not isinstance(observed_evidence, dict) or
                observed_evidence.get('frame') != expected_frame or
                observed_evidence.get('time_s') != expected_time_s):
            raise ValueError('CARLA graph original observation frame differs')
        metadata['observed_evidence'] = observed_evidence
        source_devices = {device['actor_id']: device for device in
                          observed_evidence.get('devices', [])}
        for actor in actors:
            if actor.id not in source_devices or actor.type_id != 'traffic.traffic_light':
                continue
            device = source_devices[actor.id]
            for group in device['light_boxes']:
                index = group['light_box_index']
                signal_nodes.append({'id': f'signal:{actor.id}:{index}',
                    'attributes': {'sem_class': actor.type_id,
                                   'carla_id': actor.id,
                                   'carla_light_box_index': index,
                                   'signal_group_source': 'TrafficLight.get_light_boxes',
                                   'original_device_observation': device,
                                   'light_state': device['state']}})
    graph = {
        'format': 'native-adapter-graph-v1',
        'multigraph': False,
        'metadata': metadata,
        'nodes': [_actor_node(matches[0], ego=True)] +
                 [_actor_node(actor, ego=False) for actor in others] + signal_nodes,
        'edges': [],
    }
    return (json.dumps(graph, sort_keys=True, allow_nan=False,
                       separators=(',', ':')) + '\n').encode()
