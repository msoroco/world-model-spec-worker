"""Owned 900-tick CARLA lane-change session with original four-camera capture."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from camera_capture import CameraStore, FourCameras
from native_construction import (LaneChangeController, TargetTrafficController,
                                 check_live_world, load_reviewed_site)
from native_readbacks import NativeReadbacks


class DriverInputStream:
    """Consume an independently acquired live driver-action JSONL stream.

    The operator supplies the stream and its acquisition provenance. It must be
    recorded in the same Native frame clock; an authored controller request is
    expressly invalid as a readback.
    """

    def __init__(self, path, source_id):
        self.path = Path(path)
        if self.path.is_symlink() or not self.path.is_file() or not source_id:
            raise ValueError("independent original driver-input stream required")
        self.source_id = source_id
        self.handle = self.path.open("r", encoding="utf-8")
        self.raw_rows = []

    def __call__(self, frame, elapsed):
        line = self.handle.readline()
        if not line:
            raise ValueError("original driver-input stream ended before 900 frames")
        self.raw_rows.append(line)
        row = json.loads(line)
        if row.get("source_id") != self.source_id:
            raise ValueError("original driver-input source ID changed")
        return row

    def close(self):
        self.handle.close()

    def retain(self, attempt):
        if len(self.raw_rows) != 900:
            raise ValueError("original driver-input stream has fewer than 900 frames")
        target = Path(attempt) / "original-driver-input.jsonl"
        if target.exists():
            raise ValueError("original driver-input source already retained")
        target.write_text("".join(self.raw_rows), encoding="utf-8")
        return {"path": target.name, "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "source_id": self.source_id}


class LaneChangeSession:
    def __init__(self, client, carla, map_path, map_sha256, case_id,
                 driver_input_path, driver_input_source_id):
        self.client, self.carla, self.world = client, carla, client.get_world()
        self.map_path, self.map_sha256, self.case_id = Path(map_path), map_sha256, case_id
        self.driver_input_path = driver_input_path
        self.driver_input_source_id = driver_input_source_id
        self.actor = None
        self.target_actor = None
        self.cameras = None
        self.driver_input = None
        self.restoration = None

    def __enter__(self):
        from worker_exchange import world_restore
        self.packet = load_reviewed_site(self.map_path, self.map_sha256, self.case_id)
        check_live_world(self.world, self.packet)
        # Both independent sources are checked before any world mutation.
        self.driver_input = DriverInputStream(self.driver_input_path,
                                              self.driver_input_source_id)
        self.saved_world = world_restore.snapshot(self.client)
        try:
            settings = self.world.get_settings()
            settings.synchronous_mode = True
            settings.fixed_delta_seconds = .05
            self.world.apply_settings(settings)
            x, y, z, yaw = self.packet["ego_spawn_xyz_yaw"]
            transform = self.carla.Transform(self.carla.Location(x=x, y=y, z=z),
                                             self.carla.Rotation(yaw=yaw))
            blueprint = self.world.get_blueprint_library().find(self.packet["ego_blueprint"])
            self.actor = self.world.spawn_actor(blueprint, transform)
            if self.actor is None:
                raise ValueError("original Native vehicle spawn failed")
            x, y, z, yaw = self.packet["target_spawn_xyz_yaw"]
            target_transform = self.carla.Transform(self.carla.Location(x=x, y=y, z=z),
                                                    self.carla.Rotation(yaw=yaw))
            target_blueprint = self.world.get_blueprint_library().find(
                self.packet["target_vehicle_blueprint"])
            self.target_actor = self.world.spawn_actor(target_blueprint, target_transform)
            if self.target_actor is None:
                raise ValueError("original target-lane traffic spawn failed")
            variant = self.case_id.rsplit("__", 1)[1]
            self.controller = LaneChangeController(self.packet, variant, self.carla)
            self.target_controller = TargetTrafficController(self.packet, self.carla)
            self.readbacks = NativeReadbacks(self.packet, self.case_id, self.actor,
                                              self.carla, self.driver_input)
            self.cameras = FourCameras(self.world, self.carla, self.packet, self.actor)
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def capture(self, attempt: str | Path):
        from pipeline_capture import PipelineCapture
        from worker_exchange.native_output import FrameMap
        attempt = Path(attempt)
        media = CameraStore(attempt / "original-camera-frames")
        pipeline = PipelineCapture(self.client, self.actor, attempt, self.case_id)
        frame_map = FrameMap(attempt / "video_frames.jsonl")
        target_rows = []
        completed = False
        try:
            for index in range(900):
                self.controller.step(self.actor)
                self.target_controller.step(self.target_actor)
                frame = self.world.tick()
                snapshot = self.world.get_snapshot()
                if type(frame) is not int or snapshot.frame != frame:
                    raise ValueError("original Native world frame differs from snapshot")
                elapsed = float(snapshot.timestamp.elapsed_seconds)
                if not math.isfinite(elapsed):
                    raise ValueError("original Native elapsed clock missing")
                self.readbacks.sample(frame, elapsed)
                target_transform = self.target_actor.get_transform()
                target_velocity = self.target_actor.get_velocity()
                target_rows.append({"frame": frame, "t_s": elapsed,
                    "actor_id": self.target_actor.id,
                    "position_world_xyz_m": [target_transform.location.x,
                        target_transform.location.y, target_transform.location.z],
                    "velocity_world_xyz_mps": [target_velocity.x,
                        target_velocity.y, target_velocity.z]})
                views = self.cameras.read(frame, elapsed)
                media.append(index, frame, elapsed, views)
                pipeline.capture(frame, elapsed)
                frame_map.append(frame, elapsed)
            camera_manifest = media.close()
            inventory = self.readbacks.write(attempt, "native-" + self.case_id)
            driver_source = self.driver_input.retain(attempt)
            target_path = attempt / "target-traffic-history.jsonl"
            if target_path.exists():
                raise ValueError("original target-lane traffic source already retained")
            target_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n"
                                           for row in target_rows))
            completed = True
            return {"readback_inventory": inventory,
                    "camera_manifest": camera_manifest,
                    "original_driver_input": driver_source,
                    "target_traffic": {"path": target_path.name,
                        "sha256": hashlib.sha256(target_path.read_bytes()).hexdigest()},
                    "native_frame_count": 900}
        finally:
            frame_map.close()
            pipeline.close(confirmed=completed)

    def __exit__(self, kind, value, traceback):
        from worker_exchange import world_restore
        errors = []
        if self.cameras is not None:
            try:
                self.cameras.close()
            except BaseException as exc:
                errors.append(repr(exc))
        if self.target_actor is not None:
            try:
                self.target_actor.destroy()
            except BaseException as exc:
                errors.append(repr(exc))
        if self.actor is not None:
            try:
                self.actor.destroy()
            except BaseException as exc:
                errors.append(repr(exc))
        if self.driver_input is not None:
            try:
                self.driver_input.close()
            except BaseException as exc:
                errors.append(repr(exc))
        if hasattr(self, "saved_world"):
            try:
                self.restoration = world_restore.restore(self.client, self.saved_world)
            except BaseException as exc:
                errors.append(repr(exc))
        if errors or self.restoration is None or not self.restoration.get("restored"):
            raise RuntimeError("original Native owner cleanup/restoration failed: " + "; ".join(errors))


def open_session(host, port, map_path, map_sha256, case_id,
                 driver_input_path, driver_input_source_id):
    import carla
    client = carla.Client(host, port)
    client.set_timeout(30)
    return LaneChangeSession(client, carla, map_path, map_sha256, case_id,
                             driver_input_path, driver_input_source_id)
