"""Create source-cited Native participants for the exact red-left case.

This checks proposed spawn geometry and actor calls. It does not establish the
source packet's authority or any realized right-of-way/physical outcome.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from source_bound_scene import build as bind_scene


def _xyz(value, label):
    if not isinstance(value, list) or len(value) != 3 or any(
            type(x) not in (int, float) or not math.isfinite(x) for x in value):
        raise ValueError('invalid source-cited spawn ' + label)
    return tuple(float(x) for x in value)


def _actor_spec(item, label):
    if (not isinstance(item, dict) or not item.get('blueprint_id') or
            not item.get('source_citation') or not item.get('reviewer')):
        raise ValueError('unreviewed Native actor plan: ' + label)
    location = _xyz(item.get('location_xyz_m'), label + ' location')
    rotation = _xyz(item.get('rotation_rpy_deg'), label + ' rotation')
    return location, rotation


def validate_plan(packet_path: Path, suffix: str) -> tuple[dict, dict]:
    scene = bind_scene(packet_path, suffix)
    plan = json.loads(Path(packet_path).read_text()).get('spawn_plan')
    if not isinstance(plan, dict) or set(plan) != {'ego', 'pedestrians', 'other_traffic'}:
        raise ValueError('reviewed Native participant plan missing')
    ego = plan['ego']
    position, rotation = _actor_spec(ego, 'ego')
    if ego.get('approach_lane_id') != scene['selected_approach_lane_id']:
        raise ValueError('ego spawn lane differs from exact case')
    incoming = scene['approach_direction_xy']
    center = scene['approach_lane_centers_xy'][scene['selected_approach_lane_id']]
    lateral = abs(incoming[0] * (position[1] - center[1]) -
                  incoming[1] * (position[0] - center[0]))
    reference = scene['approach_reference_xy']
    progress = sum((position[i] - reference[i]) * incoming[i] for i in (0, 1))
    heading = (math.cos(math.radians(rotation[2])), math.sin(math.radians(rotation[2])))
    if lateral > 1.75 or progress >= scene['stop_boundary_progress_m'] - 2 or sum(
            heading[i] * incoming[i] for i in (0, 1)) < .95:
        raise ValueError('ego spawn is not upstream, aligned and in selected lane')
    for key in ('pedestrians', 'other_traffic'):
        if not isinstance(plan[key], list):
            raise ValueError('Native participant list missing: ' + key)
        for index, item in enumerate(plan[key]):
            _actor_spec(item, key + str(index))
            if not item.get('route_source_citation') or not item.get('route_points_xyz_m'):
                raise ValueError('participant route source missing: ' + key)
            for point in item['route_points_xyz_m']:
                _xyz(point, key + ' route')
    if 'pedestrian' in suffix and not plan['pedestrians']:
        raise ValueError('pedestrian case lacks source-cited participant')
    if 'traffic' in suffix and not plan['other_traffic']:
        raise ValueError('traffic case lacks source-cited participant')
    return scene, plan


class NativeActors:
    def __init__(self, ego, signal, pedestrians, traffic, spawned):
        self.ego, self.signal, self.pedestrians, self.traffic = ego, signal, pedestrians, traffic
        self.spawned = spawned
    def close(self):
        for actor in reversed(self.spawned):
            actor.destroy()
        self.spawned.clear()


def create(world, packet_path: Path, suffix: str, transform_factory) -> NativeActors:
    scene, plan = validate_plan(packet_path, suffix)
    packet = json.loads(Path(packet_path).read_text())
    signal_id = str(packet['signal']['native_actor_id'])
    matches = [actor for actor in world.get_actors() if str(actor.id) == signal_id]
    if len(matches) != 1:
        raise ValueError('reviewed signal actor absent or ambiguous in Native world')
    blueprint_library = world.get_blueprint_library()
    spawned = []
    try:
        def spawn(spec):
            location, rotation = _actor_spec(spec, 'spawn')
            blueprint = blueprint_library.find(spec['blueprint_id'])
            actor = world.try_spawn_actor(blueprint, transform_factory(location, rotation))
            if actor is None:
                raise ValueError('Native participant spawn failed')
            spawned.append(actor)
            return actor
        ego = spawn(plan['ego'])
        pedestrians = [spawn(spec) for spec in plan['pedestrians']]
        traffic = [spawn(spec) for spec in plan['other_traffic']]
        return NativeActors(ego, matches[0], pedestrians, traffic, spawned)
    except Exception:
        for actor in reversed(spawned):
            actor.destroy()
        raise
