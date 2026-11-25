"""Lazy CARLA readback adapter for source-bound opposing-pass capture.

The caller owns original map review, actor/sensor creation and world cleanup.
This adapter reads only a synchronous Native tick, actor bodies and camera PNGs.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from native_history import CAMERAS


def _xyz(vector):
    values = [float(vector.x), float(vector.y), float(vector.z)]
    if not all(math.isfinite(value) for value in values):
        raise ValueError('finite original Native world vector required')
    return values


class CarlaOpposingAdapter:
    def __init__(self, world, ego, other, camera_readers, map_path,
                 *, native_map_name, source_ref, controller=None):
        if not isinstance(camera_readers, dict) or set(camera_readers) != set(CAMERAS) or not all(
                callable(camera_readers[name]) for name in CAMERAS):
            raise ValueError('four original camera readers required')
        if ego.id == other.id or not source_ref or not native_map_name:
            raise ValueError('distinct original actors and source identity required')
        self.world, self.ego, self.other = world, ego, other
        self.camera_readers = camera_readers
        self.map_path = Path(map_path)
        if not self.map_path.is_file():
            raise ValueError('original reviewed map packet required')
        self.map_sha256 = hashlib.sha256(self.map_path.read_bytes()).hexdigest()
        self.native_map_name, self.source_ref = native_map_name, source_ref
        self.controller = controller
        settings = world.get_settings()
        if settings.synchronous_mode is not True or not math.isclose(
                settings.fixed_delta_seconds, .05, abs_tol=1e-6):
            raise ValueError('original Native world must be synchronous at 20 Hz')
        if world.get_map().name != native_map_name:
            raise ValueError('original Native map name differs from reviewed site')

    def source_attestation(self):
        if hashlib.sha256(self.map_path.read_bytes()).hexdigest() != self.map_sha256:
            raise ValueError('reviewed map packet changed after adapter binding')
        if self.world.get_map().name != self.native_map_name:
            raise ValueError('original Native map changed after adapter binding')
        return {'native_origin': True, 'map_sha256': self.map_sha256,
                'native_map_name': self.native_map_name,
                'source_ref': self.source_ref}

    @staticmethod
    def _actor(actor):
        transform = actor.get_transform()
        vertices = actor.bounding_box.get_world_vertices(transform)
        if len(vertices) != 8:
            raise ValueError('eight original Native body vertices required')
        return {'actor_id': actor.id,
                'vertices_world_xyz_m': [_xyz(point) for point in vertices],
                'velocity_world_xyz_mps': _xyz(actor.get_velocity())}

    def tick(self):
        self.source_attestation()
        if self.controller is not None:
            self.controller(self.world, self.ego, self.other)
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        if type(frame) is not int or snapshot.frame != frame:
            raise ValueError('original Native world tick and snapshot differ')
        elapsed = float(snapshot.timestamp.elapsed_seconds)
        if not math.isfinite(elapsed):
            raise ValueError('finite original Native elapsed time required')
        images = {}
        for name in CAMERAS:
            image = self.camera_readers[name](frame, elapsed)
            if not isinstance(image, dict) or image.get('frame') != frame or not isinstance(
                    image.get('png_bytes'), bytes) or not image['png_bytes']:
                raise ValueError('original camera frame or PNG missing: ' + name)
            timestamp = image.get('timestamp')
            if not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp) or not math.isclose(
                    timestamp, elapsed, abs_tol=.001):
                raise ValueError('original camera timestamp differs from world tick: ' + name)
            images[name] = image['png_bytes']
        return {'native_frame': frame, 'native_elapsed_s': elapsed,
                'ego': self._actor(self.ego), 'other': self._actor(self.other),
                'cameras': images}
