"""Owned CARLA session for an original, reviewed opposing-pass site.

The reviewed packet is supplied at execution time. Importing this module never
imports CARLA or supplies a replacement site. Route requests are engineering
inputs; the retained actor bodies remain the measurements.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import queue
from pathlib import Path

from PIL import Image

from carla_adapter import CarlaOpposingAdapter
from native_history import CAMERAS, CAMERA_DIMENSIONS, capture, audit_media
from opposing_pass import construct, load_sealed, spawn_native_pair, world_routes


def review_live_site(world, map_path, expected_sha256, variant):
    """Fail before world mutation when original site review is absent or stale."""
    packet = load_sealed(map_path, expected_sha256)
    construct(packet, variant)
    world_routes(packet, variant)
    provenance = packet.get("reviewed_provenance")
    if not isinstance(provenance, dict) or not all(provenance.get(key) for key in
            ("reviewer", "source_citation", "native_map_name", "opendrive_sha256")):
        raise ValueError("original reviewed median-opening provenance required")
    native_map = world.get_map()
    if native_map.name != provenance["native_map_name"]:
        raise ValueError("live Native map differs from reviewed site")
    opendrive = native_map.to_opendrive()
    if hashlib.sha256(opendrive.encode("utf-8")).hexdigest() != provenance["opendrive_sha256"]:
        raise ValueError("live OpenDRIVE bytes differ from reviewed site")
    poses = packet.get("camera_poses_xyz_pitch_yaw")
    if not isinstance(poses, dict) or set(poses) != set(CAMERAS):
        raise ValueError("four reviewed Native camera poses required")
    for name in CAMERAS:
        pose = poses[name]
        if not isinstance(pose, list) or len(pose) != 5 or not all(
                isinstance(value, (int, float)) and math.isfinite(value) for value in pose):
            raise ValueError("reviewed Native camera pose invalid: " + name)
    return packet


class CameraReaders:
    """Frame joined four-view reader with bounded sensor queues."""

    def __init__(self, world, carla, packet, ego):
        self.sensors = []
        self.queues = {}
        self.errors = []
        try:
            for name in CAMERAS:
                width, height = CAMERA_DIMENSIONS[name]
                blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
                blueprint.set_attribute("image_size_x", str(width))
                blueprint.set_attribute("image_size_y", str(height))
                blueprint.set_attribute("fov", "90")
                x, y, z, pitch, yaw = packet["camera_poses_xyz_pitch_yaw"][name]
                transform = carla.Transform(carla.Location(x=x, y=y, z=z),
                                            carla.Rotation(pitch=pitch, yaw=yaw))
                sensor = world.spawn_actor(blueprint, transform,
                                           attach_to=ego if name == "driver_reference" else None)
                if sensor is None:
                    raise ValueError("original Native camera spawn failed: " + name)
                self.sensors.append(sensor)
                frames = queue.Queue(maxsize=4)
                self.queues[name] = frames
                def receive(image, destination=frames, label=name):
                    try:
                        destination.put_nowait(image)
                    except queue.Full:
                        self.errors.append("original camera queue overflow: " + label)
                sensor.listen(receive)
        except BaseException:
            self.close()
            raise

    def read(self, name, frame, elapsed):
        if self.errors:
            raise ValueError("; ".join(self.errors))
        width, height = CAMERA_DIMENSIONS[name]
        image = self.queues[name].get(timeout=15)
        if (image.frame != frame or image.width != width or image.height != height or
                not isinstance(image.timestamp, (int, float)) or
                not math.isclose(image.timestamp, elapsed, rel_tol=0.0, abs_tol=.001)):
            raise ValueError("original camera frame, time or dimensions differ: " + name)
        raw = image.raw_data
        if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != width * height * 4:
            raise ValueError("original camera BGRA bytes absent: " + name)
        converted = Image.frombytes("RGBA", (width, height), bytes(raw), "raw", "BGRA").convert("RGB")
        buffer = io.BytesIO()
        converted.save(buffer, format="PNG")
        return {"frame": frame, "timestamp": image.timestamp,
                "png_bytes": buffer.getvalue()}

    def close(self):
        errors = []
        for sensor in reversed(self.sensors):
            try:
                sensor.stop()
                sensor.destroy()
            except BaseException as exc:
                errors.append(repr(exc))
        self.sensors.clear()
        if errors:
            raise RuntimeError("original camera cleanup failed: " + "; ".join(errors))


class OpposingSession:
    def __init__(self, world, carla, map_path, map_sha256, variant, client=None):
        self.world, self.carla = world, carla
        self.client = client
        self.map_path, self.map_sha256, self.variant = Path(map_path), map_sha256, variant
        self.original_settings = world.get_settings()
        self.actors = {}
        self.cameras = None
        self.restoration_verified = False

    def __enter__(self):
        packet = review_live_site(self.world, self.map_path, self.map_sha256, self.variant)
        self.packet = packet
        try:
            settings = self.world.get_settings()
            settings.synchronous_mode = True
            settings.fixed_delta_seconds = .05
            self.world.apply_settings(settings)
            def transform(pose):
                x, y, z, yaw, pitch, roll = pose
                return self.carla.Transform(self.carla.Location(x=x, y=y, z=z),
                                            self.carla.Rotation(yaw=yaw, pitch=pitch, roll=roll))
            pair = spawn_native_pair(self.world, self.world.get_blueprint_library(), packet,
                                     self.variant, transform)
            self.actors = pair["actors"]
            self.route = world_routes(packet, self.variant)
            self.cameras = CameraReaders(self.world, self.carla, packet, self.actors["ego"])
            readers = {name: lambda frame, elapsed, label=name: self.cameras.read(label, frame, elapsed)
                       for name in CAMERAS}
            self.adapter = CarlaOpposingAdapter(
                self.world, self.actors["ego"], self.actors["other"], readers,
                self.map_path, native_map_name=packet["reviewed_provenance"]["native_map_name"],
                source_ref=packet["reviewed_provenance"]["source_citation"],
                controller=self.control)
            self._target = {"ego": 1, "other": 1}
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def control(self, world, ego, other):
        for role, actor in (("ego", ego), ("other", other)):
            points = self.route[role + "_world_xyz_m"]
            position = actor.get_transform().location
            target = self._target[role]
            while target < len(points)-1 and math.hypot(points[target][0]-position.x,
                                                        points[target][1]-position.y) < 2:
                target += 1
            self._target[role] = target
            dx, dy = points[target][0]-position.x, points[target][1]-position.y
            yaw = math.radians(actor.get_transform().rotation.yaw)
            error = (math.atan2(dy, dx)-yaw+math.pi) % (2*math.pi)-math.pi
            steer = max(-.65, min(.65, 1.2*error))
            arrived = math.hypot(points[-1][0]-position.x, points[-1][1]-position.y) < 1
            actor.apply_control(self.carla.VehicleControl(
                throttle=0 if arrived else .30, brake=1 if arrived else 0,
                steer=steer))

    def capture(self, output, media_output):
        pipeline = frame_map = None
        attempt = Path(output).parent
        if self.client is not None:
            from pipeline_capture import PipelineCapture
            from worker_exchange.native_output import FrameMap
            case_id = json.loads((attempt / "config.json").read_text())["selected_case_id"]
            pipeline = PipelineCapture(self.client, self.actors["ego"], attempt, case_id)
            frame_map = FrameMap(attempt / "video_frames.jsonl")
            def observe(frame, elapsed):
                pipeline.capture(frame, elapsed)
                frame_map.append(frame, elapsed)
            self.adapter.observer = observe
        succeeded = False
        try:
            receipt = capture(self.adapter, self.map_path, self.map_sha256, self.variant,
                              output, frames=900, media_output=media_output)
            succeeded = True
        finally:
            self.adapter.observer = None
            if frame_map is not None:
                frame_map.close()
            if pipeline is not None:
                pipeline.close(confirmed=succeeded)
        receipt["media_audit"] = audit_media(output, receipt["sha256"], media_output,
                                              receipt["camera_manifest"]["sha256"])
        return receipt

    def __exit__(self, kind, value, traceback):
        errors = []
        if self.cameras is not None:
            try:
                self.cameras.close()
            except BaseException as exc:
                errors.append(repr(exc))
        for actor in reversed(list(self.actors.values())):
            try:
                actor.destroy()
            except BaseException as exc:
                errors.append(repr(exc))
        try:
            self.world.apply_settings(self.original_settings)
            now = self.world.get_settings()
            self.restoration_verified = (now.synchronous_mode == self.original_settings.synchronous_mode
                and now.fixed_delta_seconds == self.original_settings.fixed_delta_seconds)
        except BaseException as exc:
            errors.append(repr(exc))
        if errors or not self.restoration_verified:
            raise RuntimeError("original Native session restoration failed: " + "; ".join(errors))


def open_session(host, port, map_path, map_sha256, variant):
    """Connect lazily; opening a session still requires independently reviewed bytes."""
    import carla
    client = carla.Client(host, port)
    client.set_timeout(30)
    return OpposingSession(client.get_world(), carla, map_path, map_sha256, variant,
                           client=client)
