"""Lazy Native CARLA driveway acquisition for an exact LVMC case.

The reviewed packet supplies real map, mouth, camera and person/business facts.
This code records observations; it cannot establish legal status or a verdict.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
from pathlib import Path
import threading
import time
import zipfile

from driveway_construction import CAMERAS, build_plan, validate_survey
from driveway_measurements import ASSIGNMENT_ID, measure
from parking_controller import ParkingController


VIEWS = (("overview", 1920, 1080), ("approach", 1280, 720),
         ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))


def _triple(value, label):
    if (not isinstance(value, list) or len(value) != 3 or
            any(type(x) not in (int, float) or not math.isfinite(x) for x in value)):
        raise ValueError("reviewed " + label + " triple required")
    return tuple(float(x) for x in value)


def _camera_plan(survey):
    cameras = survey.get("cameras")
    if not isinstance(cameras, list) or len(cameras) != 4:
        raise ValueError("reviewed four-camera plan required")
    for camera, expected in zip(cameras, VIEWS):
        if tuple(camera.get(key) for key in ("name", "width", "height")) != expected:
            raise ValueError("reviewed camera profile differs")
        _triple(camera.get("location_xyz_m"), "camera location")
        _triple(camera.get("rotation_rpy_deg"), "camera rotation")
        if (type(camera.get("fov_deg")) not in (int, float) or
                not 1 <= camera["fov_deg"] <= 170 or not camera.get("pose_source")):
            raise ValueError("reviewed camera pose and field of view required")
    return cameras


def validate_packet(packet_path, case_id):
    survey, hashes, _, _, _ = validate_survey(packet_path)
    if survey.get("case_id") != case_id or not case_id.startswith(ASSIGNMENT_ID + "__"):
        raise ValueError("reviewed survey exact case differs")
    plan = json.loads((Path(__file__).parent / "case-plan.json").read_text())
    case, = [row for row in plan["cases"] if row["case_id"] == case_id]
    for name in ("driveway_kind", "activity", "position_target", "driver_relationship",
                 "necessity_or_postal_context"):
        if survey.get("observed_conditions", {}).get(name) != case[name]:
            raise ValueError("reviewed original condition differs: " + name)
    _camera_plan(survey)
    _triple(survey.get("spawn_xyz_m"), "vehicle spawn")
    _triple(survey.get("spawn_rpy_deg"), "vehicle rotation")
    return survey, hashes


def _transform(carla, xyz, rpy):
    x, y, z = _triple(xyz, "position")
    roll, pitch, yaw = _triple(rpy, "rotation")
    return carla.Transform(carla.Location(x=x, y=y, z=z),
                           carla.Rotation(roll=roll, pitch=pitch, yaw=yaw))


class CameraBuffer:
    def __init__(self):
        self.condition = threading.Condition()
        self.frames = {}
        self.errors = []

    def receive(self, name, width, height, image):
        try:
            if (type(image.frame) is not int or image.width != width or
                    image.height != height or len(image.raw_data) != width * height * 4):
                raise ValueError("original camera shape or frame invalid")
            from PIL import Image
            rgb = Image.frombytes("RGBA", (width, height), bytes(image.raw_data),
                                  "raw", "BGRA").convert("RGB")
            data = io.BytesIO()
            rgb.save(data, format="PNG")
            with self.condition:
                key = (name, image.frame)
                if key in self.frames:
                    raise ValueError("duplicate original camera frame")
                self.frames[key] = data.getvalue()
                self.condition.notify_all()
        except Exception as error:
            with self.condition:
                self.errors.append(error)
                self.condition.notify_all()

    def read(self, name, frame, timeout_s=15):
        deadline = time.monotonic() + timeout_s
        with self.condition:
            while (name, frame) not in self.frames and not self.errors:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ValueError("original camera frame missing: " + name)
                self.condition.wait(remaining)
            if self.errors:
                raise ValueError("original camera callback failed: " + str(self.errors[0]))
            return self.frames.pop((name, frame))


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def capture(case_id, packet_path, output, *, host="localhost", port=2000,
            approach_direction=1):
    """Capture a sealed original attempt; output must not already exist."""
    packet_path, output = Path(packet_path), Path(output)
    survey, hashes = validate_packet(packet_path, case_id)
    plan = build_plan(packet_path, case_id, approach_direction=approach_direction)
    map_path = packet_path.resolve().parent / survey["sources"]["opendrive"]["path"]
    map_bytes = map_path.read_bytes()
    if hashlib.sha256(map_bytes).hexdigest() != hashes["opendrive"]:
        raise ValueError("reviewed map source changed before Native launch")
    if output.exists():
        raise ValueError("retain existing Native attempt")
    output.mkdir(parents=True)
    import carla
    client = carla.Client(host, int(port))
    client.set_timeout(30)
    world = client.get_world()
    if world.get_settings().no_rendering_mode:
        raise ValueError("Native world rendering disabled")
    if hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest() != hashes["opendrive"]:
        raise ValueError("loaded Native map differs from reviewed OpenDRIVE")
    prior = world.get_settings()
    actor, sensors, archives, pipeline = None, [], {}, None
    cameras = CameraBuffer()
    complete = False
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.no_rendering_mode = False
        world.apply_settings(settings)
        library = world.get_blueprint_library()
        bp = library.find(survey["vehicle_blueprint_id"])
        bp.set_attribute("role_name", "lvmc-driveway-ego")
        actor = world.try_spawn_actor(bp, _transform(carla, survey["spawn_xyz_m"],
                                                       survey["spawn_rpy_deg"]))
        if actor is None:
            raise ValueError("reviewed driveway vehicle spawn failed")
        from pipeline_capture import PipelineCapture
        pipeline = PipelineCapture(client, actor, output.parent, case_id)
        for camera in survey["cameras"]:
            bp = library.find("sensor.camera.rgb")
            for key, value in (("image_size_x", camera["width"]),
                               ("image_size_y", camera["height"]),
                               ("fov", camera["fov_deg"]), ("sensor_tick", 0.0)):
                bp.set_attribute(key, str(value))
            sensor = world.spawn_actor(bp, _transform(carla, camera["location_xyz_m"],
                                                       camera["rotation_rpy_deg"]))
            sensors.append((camera["name"], sensor))
            sensor.listen(lambda image, n=camera["name"], w=camera["width"],
                          h=camera["height"]: cameras.receive(n, w, h, image))
        archives = {name: zipfile.ZipFile(output / (name + ".zip"), "w", zipfile.ZIP_STORED)
                    for name in CAMERAS}
        controller = ParkingController(plan)
        trace = []
        camera_map = []
        first_time = None
        last_frame = None
        for index in range(900):
            pose = actor.get_transform()
            velocity = actor.get_velocity()
            speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
            now = float(world.get_snapshot().timestamp.elapsed_seconds)
            control = controller.step(xy_m=[pose.location.x, pose.location.y],
                                      yaw_rad=math.radians(pose.rotation.yaw),
                                      speed_mps=speed, time_s=now)
            actor.apply_control(carla.VehicleControl(throttle=control["throttle"],
                                                     brake=control["brake"], steer=control["steer"]))
            frame = world.tick()
            snapshot = world.get_snapshot()
            if snapshot.frame != frame or (last_frame is not None and frame != last_frame + 1):
                raise ValueError("original Native frame gap")
            last_frame = frame
            elapsed = float(snapshot.timestamp.elapsed_seconds)
            if first_time is None:
                first_time = elapsed
            if abs(elapsed - first_time - index / 20) > .002:
                raise ValueError("original Native cadence drift")
            pipeline.capture(frame, elapsed)
            vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
            if len(vertices) != 8:
                raise ValueError("original Native body vertices incomplete")
            velocity = actor.get_velocity()
            speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
            state = survey["observed_conditions"]["activity"] if control["phase"] == "hold" else control["phase"]
            trace.append({"frame": index, "carla_frame": frame, "time_s": index / 20,
                          "vehicle_vertices": [[float(v.x), float(v.y), float(v.z)] for v in vertices],
                          "speed_mps": speed, "control_state": state})
            camera_map.append({"frame": index, "carla_frame": frame, "time_s": index / 20,
                               "native_time_s": elapsed,
                               "camera_names": list(CAMERAS)})
            for name in CAMERAS:
                archives[name].writestr(f"{index:04d}-{frame}.png", cameras.read(name, frame))
        if hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest() != hashes["opendrive"]:
            raise ValueError("Native map changed during attempt")
        for archive in archives.values():
            archive.close()
        archives = {}
        (output / "road.xodr").write_bytes(map_bytes)
        context = {"case_id": case_id, "driveway_kind": survey["driveway_kind"],
                   "map_sha256": hashes["opendrive"],
                   "mouth_start_xy": survey["mouth_start_xy_m"],
                   "mouth_end_xy": survey["mouth_end_xy_m"]}
        for name, source in (("mouth_source", "mouth"), ("frontage_source", "frontage"),
                             ("driveway_use_source", "driveway_use"),
                             ("responsible_person_source", "responsible_person"),
                             ("relationship_source", "relationship"),
                             ("purpose_source", "purpose"),
                             ("traffic_direction_source", "traffic_direction"),
                             ("postal_status_source", "postal_status")):
            context[name] = survey["sources"][source]
        (output / "reviewed-context.json").write_text(json.dumps(context, sort_keys=True) + "\n")
        (output / "body-control-trace.jsonl").write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in trace))
        (output / "camera-frame-map.jsonl").write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in camera_map))
        receipt = {"assignment_id": ASSIGNMENT_ID, "case_id": case_id,
                   "source_kind": "native_pending_restoration", "diagnostic_fixture": False,
                   "context_sha256": _sha(output / "reviewed-context.json"),
                   "trace_sha256": _sha(output / "body-control-trace.jsonl"),
                   "map_sha256": _sha(output / "road.xodr"), "frame_count": 900, "fps": 20,
                   "reviewed_survey_sha256": _sha(packet_path),
                   "camera_source_sha256": {name: _sha(output / (name + ".zip")) for name in CAMERAS}}
        (output / "capture-receipt.json").write_text(json.dumps(receipt, sort_keys=True) + "\n")
        complete = True
    finally:
        errors = []
        for archive in archives.values():
            try:
                archive.close()
            except Exception as error:
                errors.append(error)
        if pipeline is not None:
            try:
                pipeline.close(confirmed=complete)
            except Exception as error:
                errors.append(error)
        if actor is not None:
            try:
                actor.apply_control(carla.VehicleControl(throttle=0, brake=1))
            except Exception as error:
                errors.append(error)
        for _, sensor in reversed(sensors):
            try:
                sensor.stop()
                sensor.destroy()
            except Exception as error:
                errors.append(error)
        if actor is not None:
            try:
                actor.destroy()
            except Exception as error:
                errors.append(error)
        try:
            world.apply_settings(prior)
            restored = world.get_settings()
            if (restored.synchronous_mode != prior.synchronous_mode or
                    restored.fixed_delta_seconds != prior.fixed_delta_seconds or
                    restored.no_rendering_mode != prior.no_rendering_mode):
                errors.append(ValueError("Native world settings restoration readback differs"))
        except Exception as error:
            errors.append(error)
        if not complete or errors:
            # Retain failed originals for forensic review; do not claim closure.
            (output / "capture-incomplete.txt").write_text("Native capture did not complete\n")
        if errors:
            raise RuntimeError("Native driveway cleanup failed: " + "; ".join(map(str, errors)))
    receipt["source_kind"] = "original_native_capture"
    receipt["restoration_verified"] = True
    (output / "capture-receipt.json").write_text(json.dumps(receipt, sort_keys=True) + "\n")
    try:
        measured = measure(case_id, output / "reviewed-context.json",
                           output / "body-control-trace.jsonl", output / "capture-receipt.json",
                           output / "road.xodr")
    except Exception:
        receipt["source_kind"] = "native_measurement_failed"
        (output / "capture-receipt.json").write_text(json.dumps(receipt, sort_keys=True) + "\n")
        (output / "capture-incomplete.txt").write_text("Native measurement did not complete\n")
        raise
    (output / "driveway-measurement.json").write_text(json.dumps(measured, sort_keys=True) + "\n")
    return measured
