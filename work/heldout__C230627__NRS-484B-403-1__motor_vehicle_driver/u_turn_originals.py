"""Retain unmodified Native actor readbacks for saved-only U-turn measurement."""

import json
from math import hypot, isfinite
from pathlib import Path

from u_turn_measurement import PROHIBITIONS


def _body(actor):
    location = actor.get_transform().location
    extent = actor.bounding_box.extent
    velocity = actor.get_velocity()
    values = [float(location.x), float(location.y), float(extent.x),
              float(extent.y), float(velocity.x), float(velocity.y)]
    if not all(isfinite(value) for value in values) or min(values[2:4]) <= 0:
        raise ValueError("Native actor body or velocity invalid")
    return {'x_m': values[0], 'y_m': values[1],
            'body_radius_m': hypot(values[2], values[3]),
            'speed_mps': hypot(values[4], values[5])}


class UTurnSourceRecorder:
    def __init__(self, directory, ego, participants, scene, *, device=None):
        self.root = Path(directory)
        self.ego = ego
        self.participants = dict(participants)
        if set(self.participants) != {'oncoming', 'following'}:
            raise ValueError("Original oncoming and following actors required")
        identities = [int(ego.id)] + [int(a.id) for a in self.participants.values()]
        if len(set(identities)) != 3:
            raise ValueError("Original actor identities must differ")
        self.ids = {role: str(int(actor.id)) for role, actor in self.participants.items()}
        context = {
            'format': 'worker-u-turn-original-context',
            'approach_road_id': scene['road_id'],
            'approach_lane_id': scene['approach_lane_id'],
            'opposite_lane_id': scene['opposite_lane_id'],
            'participant_roles': {
                self.ids[role]: {
                    'role': role,
                    'source_ref': 'u_turn_motion.jsonl#participants/' + self.ids[role]}
                for role in ('oncoming', 'following')},
            'prohibitions': {
                law: {'value': None, 'source_ref': None} for law in PROHIBITIONS},
            'legal_safety_judgment': None,
            'physical_completion_verified': False}
        path = self.root / 'u_turn_context.json'
        if path.exists():
            raise ValueError("Retain prior original U-turn context")
        path.write_text(json.dumps(context, indent=2, allow_nan=False) + '\n')
        if device is not None:
            observation = {
                'mapped_no_u_turn_device': {
                    'landmark_id': device['landmark_id'],
                    'road_id': device['road_id'],
                    'distance_to_approach_m': device['distance_to_approach_m'],
                    'source_fields': device['source_fields'],
                    'official_device_status': None,
                    'governing_lane_status': None,
                    'pixel_visibility_status': None}}
            (self.root/'u_turn_device.json').write_text(
                json.dumps(observation, indent=2, allow_nan=False)+'\n')
        self.stream = (self.root / 'u_turn_motion.jsonl').open('x', encoding='utf-8')
        self.previous = None

    def append(self, frame, time_s):
        if type(frame) is not int or type(time_s) not in (int, float) or not isfinite(time_s):
            raise ValueError("Native U-turn frame/time invalid")
        if self.previous is not None and (frame != self.previous[0] + 1 or
                abs(time_s - self.previous[1] - .05) > 1e-4):
            raise ValueError("Native U-turn 20 Hz source discontinuity")
        transform = self.ego.get_transform()
        yaw = float(transform.rotation.yaw)
        if not isfinite(yaw):
            raise ValueError("Native U-turn yaw invalid")
        row = {'frame': frame, 'time_s': time_s,
               'ego_id': int(self.ego.id),
               'ego': _body(self.ego), 'ego_yaw_deg': yaw,
               'participants': {self.ids[role]: _body(actor)
                                for role, actor in self.participants.items()}}
        self.stream.write(json.dumps(row, allow_nan=False) + '\n')
        self.stream.flush()
        self.previous = frame, time_s
        return row

    def close(self):
        self.stream.close()
