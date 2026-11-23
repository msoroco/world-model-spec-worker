"""Derive engineering controller inputs from original Native bodies and a reviewed site.

Conflict zones are conservative source-cited physical areas. Their overlap flags
request a wait; they do not decide statutory right-of-way.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from red_left_turn_controller import Observation
from source_bound_scene import build as bind_scene


def _xy(value, name):
    if not isinstance(value, (list, tuple)) or len(value) < 2 or any(
            type(x) not in (int, float) or not math.isfinite(x) for x in value[:2]):
        raise ValueError('invalid original/source XY: ' + name)
    return float(value[0]), float(value[1])


def _zone(value, name):
    if not isinstance(value, dict) or not value.get('source_citation') or not value.get('reviewer'):
        raise ValueError('unreviewed conflict/exit source: ' + name)
    low = _xy(value.get('min_xy'), name + ' min')
    high = _xy(value.get('max_xy'), name + ' max')
    if any(high[i] <= low[i] for i in (0, 1)):
        raise ValueError('empty source conflict zone: ' + name)
    return low, high


def plan(packet_path: Path, suffix: str) -> tuple[dict, dict]:
    scene = bind_scene(packet_path, suffix)
    packet = json.loads(Path(packet_path).read_text())
    value = packet.get('observation_plan')
    if not isinstance(value, dict) or set(value) != {'pedestrian_zone', 'traffic_zone', 'exit_gate'}:
        raise ValueError('source-cited observation plan missing')
    zones = {name: _zone(value[name], name) for name in ('pedestrian_zone', 'traffic_zone')}
    gate = value['exit_gate']
    if not isinstance(gate, dict) or not gate.get('source_citation') or not gate.get('reviewer'):
        raise ValueError('unreviewed receiving-road exit gate')
    gate_point = _xy(gate.get('point_xy'), 'exit gate')
    return scene, {'zones': zones, 'exit_point_xy': gate_point,
                   'signal_actor_id': str(packet['signal']['native_actor_id']),
                   'source_packet_sha256': scene['source_packet_sha256']}


def _body_box(actor, name):
    vertices = actor.get('body_vertices_xyz_m')
    if not isinstance(vertices, list) or len(vertices) < 4:
        raise ValueError('original full body missing: ' + name)
    points = [_xy(v, name + ' vertex') for v in vertices]
    return (min(v[0] for v in points), min(v[1] for v in points)), (
        max(v[0] for v in points), max(v[1] for v in points))


def _overlaps(actor, zone, name):
    low, high = _body_box(actor, name)
    zone_low, zone_high = zone
    return all(low[i] <= zone_high[i] and high[i] >= zone_low[i] for i in (0, 1))


def from_frame(frame: dict, scene: dict, observation_plan: dict) -> Observation:
    if (frame.get('origin') != 'native_world_snapshot' or
            observation_plan['source_packet_sha256'] != scene['source_packet_sha256']):
        raise ValueError('original frame/observation source differs')
    if str(frame.get('signal_actor_id')) != observation_plan['signal_actor_id']:
        raise ValueError('original signal actor differs from reviewed site')
    ego = frame.get('ego')
    if not isinstance(ego, dict):
        raise ValueError('original ego body missing')
    vertices = ego.get('body_vertices_xyz_m')
    if not isinstance(vertices, list) or len(vertices) < 4:
        raise ValueError('original ego body vertices missing')
    direction = scene['approach_direction_xy']
    reference = scene['approach_reference_xy']
    front = max(sum((_xy(v, 'ego vertex')[i] - reference[i]) * direction[i]
                    for i in (0, 1)) for v in vertices)
    distance = scene['stop_boundary_progress_m'] - front
    velocity = ego.get('velocity_xyz_mps')
    if not isinstance(velocity, list) or len(velocity) < 3 or any(
            type(x) not in (int, float) or not math.isfinite(x) for x in velocity[:3]):
        raise ValueError('original ego velocity missing')
    speed = math.sqrt(sum(float(x) ** 2 for x in velocity[:3]))
    for key in ('pedestrians', 'other_traffic'):
        if not isinstance(frame.get(key), list):
            raise ValueError('original participant list missing: ' + key)
    pedestrian = any(_overlaps(actor, observation_plan['zones']['pedestrian_zone'], 'pedestrian')
                     for actor in frame['pedestrians'])
    traffic = any(_overlaps(actor, observation_plan['zones']['traffic_zone'], 'traffic')
                  for actor in frame['other_traffic'])
    center = _xy(ego.get('location_xyz_m'), 'ego center')
    exit_point = observation_plan['exit_point_xy']
    outgoing = scene['receiving_direction_xy']
    exited = sum((center[i] - exit_point[i]) * outgoing[i] for i in (0, 1)) >= 0
    time_s = frame.get('time_s')
    if type(time_s) not in (int, float) or not math.isfinite(time_s):
        raise ValueError('original frame time missing')
    red = str(frame.get('signal_state')).rsplit('.', 1)[-1].lower() == 'red'
    return Observation(float(time_s), float(distance), speed,
                       'steady_red_alone' if red else 'other', pedestrian, traffic, exited)
