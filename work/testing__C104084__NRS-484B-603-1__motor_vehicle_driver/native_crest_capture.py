"""Join original Native ticks to two vehicles and four camera images.

The caller owns CARLA world setup, actor spawning, camera encoders and lifecycle.
This adapter records only observations supplied for the same world tick; it does
not create motion, pixels, a speed limit, or a legal outcome.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from saved_crest_audit import CAMERAS, FRAME_COUNT


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


class NativeTickRecorder:
    def __init__(self, *, ego_actor_id, other_actor_id, native_capture_ref):
        if not all(isinstance(value, str) and value.strip() for value in
                   (ego_actor_id, other_actor_id, native_capture_ref)):
            raise ValueError('original actor IDs and Native capture reference required')
        if ego_actor_id == other_actor_id:
            raise ValueError('distinct original vehicle actors required')
        self.ego_actor_id = ego_actor_id
        self.other_actor_id = other_actor_id
        self.native_capture_ref = native_capture_ref
        self.motion = []
        self.frame_map = []

    def append(self, *, world_frame, ego, other, camera_frames):
        """Retain one synchronized tick after caller observes both actor bodies.

        `ego` and `other` are original per-tick observation dictionaries. Camera
        values are original image objects with a `frame` property. Pixel bytes
        are retained by the caller's video encoder and audited after encoding.
        """
        index = len(self.motion)
        if index >= FRAME_COUNT:
            raise ValueError('capture exceeds planned 900 Native frames')
        if type(world_frame) is not int or world_frame < 0:
            raise ValueError('original integer Native world frame required')
        if self.motion and world_frame <= self.motion[-1]['frame_id']:
            raise ValueError('Native world frames must increase')
        if not isinstance(camera_frames, dict) or set(camera_frames) != set(CAMERAS):
            raise ValueError('all four original camera images required')
        if any(getattr(camera_frames[name], 'frame', None) != world_frame for name in CAMERAS):
            raise ValueError('camera image and Native world tick differ')
        if not isinstance(ego, dict) or not isinstance(other, dict):
            raise ValueError('two original actor observations required')
        if ego.get('actor_id') != self.ego_actor_id or other.get('actor_id') != self.other_actor_id:
            raise ValueError('original vehicle actor identity differs')
        fields = (ego.get('station_m'), ego.get('speed_mps'),
                  other.get('station_m'), ego.get('body_clearance_m'))
        if not all(_finite(value) for value in fields):
            raise ValueError('finite original station, speed and clearance required')
        if ego['speed_mps'] < 0 or ego['body_clearance_m'] < 0:
            raise ValueError('negative original speed or body clearance')
        if self.motion and (ego['station_m'] < self.motion[-1]['ego_s_m'] or
                            other['station_m'] > self.motion[-1]['other_s_m']):
            raise ValueError('original vehicle reversed on bound crest routes')
        for actor in (ego, other):
            if not isinstance(actor.get('source_ref'), str) or not actor['source_ref'].strip():
                raise ValueError('original actor observation source required')
            if str(world_frame) not in actor['source_ref']:
                raise ValueError('original actor source must identify Native frame')
        time_s = index / 20
        frame = {'frame_id': world_frame, 'time_s': time_s,
                 'ego_s_m': ego['station_m'], 'ego_speed_mps': ego['speed_mps'],
                 'other_s_m': other['station_m'],
                 'body_clearance_m': ego['body_clearance_m'],
                 'ego_actor_id': self.ego_actor_id,
                 'other_actor_id': self.other_actor_id,
                 'other_source_ref': other['source_ref'],
                 'source_ref': ego['source_ref']}
        if 'position' in ego and 'heading_deg' in ego:
            position = ego['position']
            heading = ego['heading_deg']
            if (not isinstance(position, dict) or set(position) != {'x', 'y', 'z'}
                    or not all(_finite(position[key]) for key in position)
                    or not _finite(heading)):
                raise ValueError('finite original ego pose required')
            frame['position'] = position
            frame['heading_deg'] = heading
        identity = {'video_frame': index, 'carla_frame': world_frame, 'time_s': time_s}
        self.motion.append(frame)
        self.frame_map.append(identity)
        return identity

    def write(self, directory):
        """Write only complete original motion and frame-map source files."""
        if len(self.motion) != FRAME_COUNT:
            raise ValueError('complete 900-frame Native capture required')
        root = Path(directory)
        if not root.is_dir() or any((root / name).exists() for name in
                                    ('motion.json', 'frame-map.jsonl')):
            raise ValueError('fresh capture-source destination required')
        motion_path = root / 'motion.json'
        frame_path = root / 'frame-map.jsonl'
        motion_path.write_text(json.dumps(self.motion, allow_nan=False) + '\n', encoding='utf-8')
        frame_path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n'
                                      for row in self.frame_map), encoding='utf-8')
        return {'motion_source': str(motion_path), 'frame_map_source': str(frame_path),
                'native_capture_ref': self.native_capture_ref,
                'frame_count': FRAME_COUNT,
                'camera_status': 'same_tick_identity_only; encoder bytes require saved decode'}
