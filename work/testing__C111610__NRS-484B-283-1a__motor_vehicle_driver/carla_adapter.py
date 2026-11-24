"""Lazy original-world adapter for the exact crosswalk capture writer.

The caller owns the world lease, actors, sensors and cleanup. Camera readers
must return PNG bytes from the corresponding original sensor frame. This code
does not claim that a site survey, actor motion or visible pixels were accepted.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from native_capture import CAMERAS


class CarlaNativeAdapter:
    def __init__(self, world, ego, pedestrian, camera_readers, site_path,
                 source_ref, controller=None):
        if set(camera_readers) != set(CAMERAS) or not all(
                callable(camera_readers[name]) for name in CAMERAS):
            raise ValueError("four original sensor readers required")
        if not source_ref or not Path(site_path).is_file():
            raise ValueError("original site source reference required")
        self.world = world
        self.ego = ego
        self.pedestrian = pedestrian
        self.camera_readers = camera_readers
        self.site_path = Path(site_path)
        self.source_ref = source_ref
        self.controller = controller
        self.site_sha256 = hashlib.sha256(self.site_path.read_bytes()).hexdigest()
        self.map_name = world.get_map().name
        settings = world.get_settings()
        if (settings.synchronous_mode is not True or
                not math.isclose(settings.fixed_delta_seconds, 0.05,
                                 abs_tol=1e-6)):
            raise ValueError("original world must be synchronous at 20 Hz")
        if not isinstance(ego.id, int) or not isinstance(pedestrian.id, int) or ego.id == pedestrian.id:
            raise ValueError("separate original participant actors required")

    def source_attestation(self):
        if hashlib.sha256(self.site_path.read_bytes()).hexdigest() != self.site_sha256:
            raise ValueError("original site source changed after adapter binding")
        if self.world.get_map().name != self.map_name:
            raise ValueError("original map changed after adapter binding")
        return {"native_origin": True, "map_name": self.map_name,
                "site_sha256": self.site_sha256, "source_ref": self.source_ref}

    @staticmethod
    def _xy(actor):
        location = actor.get_transform().location
        xy = [float(location.x), float(location.y)]
        if not all(math.isfinite(value) for value in xy):
            raise ValueError("original participant pose invalid")
        return xy

    def tick(self):
        self.source_attestation()
        if self.controller is not None:
            self.controller(self.world, self.ego, self.pedestrian)
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        if snapshot.frame != frame:
            raise ValueError("original world tick/snapshot frame mismatch")
        elapsed = float(snapshot.timestamp.elapsed_seconds)
        if not math.isfinite(elapsed):
            raise ValueError("original world time unavailable")
        images = {}
        for name in CAMERAS:
            image = self.camera_readers[name](frame)
            if (not isinstance(image, dict) or image.get("frame") != frame
                    or not isinstance(image.get("png_bytes"), bytes)
                    or not image["png_bytes"]):
                raise ValueError("original camera frame or PNG missing: " + name)
            images[name] = image["png_bytes"]
        control = self.ego.get_control()
        brake = float(control.brake)
        if not math.isfinite(brake) or not 0 <= brake <= 1:
            raise ValueError("original ego brake readback invalid")
        return {"native_frame": frame, "native_elapsed_s": elapsed,
                "ego": {"actor_id": self.ego.id,
                        "classification": "motor_vehicle_driver",
                        "body_center_xy_m": self._xy(self.ego),
                        "brake": brake >= 0.5},
                "pedestrian": {"actor_id": self.pedestrian.id,
                               "classification": "pedestrian",
                               "body_center_xy_m": self._xy(self.pedestrian)},
                "cameras": images}
