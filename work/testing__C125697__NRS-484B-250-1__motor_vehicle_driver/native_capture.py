"""Source-gated original C125697 acquisition with owned CARLA resources.

The caller supplies a reviewed original packet. Diagnostic fixtures may test
this module's guards but cannot authorize a physical delivery attempt.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import math
from pathlib import Path
from queue import Empty, Queue
import shutil
import subprocess

from PIL import Image

import median_opening

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
DIMENSIONS = {"overview": (1920, 1080), "approach": (1280, 720),
              "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source(packet_dir: Path, ref: dict, label: str) -> tuple[Path, bytes]:
    if not isinstance(ref, dict) or not ref.get("path") or not ref.get("sha256") or not ref.get("citation"):
        raise ValueError("reviewed original " + label + " reference required")
    candidate = packet_dir / ref["path"]
    path = candidate.resolve()
    if (candidate.is_symlink() or not path.is_relative_to(packet_dir) or
            not path.is_file()):
        raise ValueError("reviewed original " + label + " source missing")
    data = path.read_bytes()
    if _sha(data) != ref["sha256"]:
        raise ValueError("reviewed original " + label + " source changed")
    return path, data


def reviewed_packet(packet_path: Path, world, location_factory) -> tuple[dict, dict[str, bytes]]:
    packet_path = Path(packet_path)
    if packet_path.is_symlink() or not packet_path.is_file():
        raise ValueError("reviewed original site packet absent")
    packet_dir = packet_path.parent.resolve()
    scene = json.loads(packet_path.read_text())
    if scene.get("review_status") != "reviewed_original" or not scene.get("reviewer"):
        raise ValueError("reviewed original site and reviewer required")
    if scene.get("cell_id") != "C125697" or scene.get("actor") != "motor_vehicle_driver":
        raise ValueError("wrong reviewed site identity")
    live_map = world.get_map().to_opendrive()
    median_opening.validate_scene(scene, live_map)
    median_opening.bind_native_map(world.get_map(), scene, location_factory)
    sources = {}
    for name in ("device_inventory", "highway_identity"):
        _, sources[name] = _source(packet_dir, scene.get("source_refs", {}).get(name), name)
    devices = json.loads(sources["device_inventory"])
    highways = json.loads(sources["highway_identity"])
    signal = scene["governing_signal"]
    if (type(signal.get("actor_id")) is not int or
            devices.get("governing_signal_actor_id") != signal["actor_id"] or
            devices.get("controlled_approach_road_ids") != signal["controlled_approach_road_ids"]):
        raise ValueError("original governing-device inventory does not match selected approaches")
    if (highways.get("ego_highway") != scene["ego_highway"] or
            highways.get("other_highway") != scene["other_highway"] or
            highways.get("public_access_confirmed") is not True):
        raise ValueError("original public-highway identity source does not match crossing")
    if not scene.get("opposing_left_turn_excluded_source"):
        raise ValueError("original opposing-turn source review required")
    if not scene.get("subsection_4_applicability_review"):
        raise ValueError("subsection 4 applicability review required")
    cameras = scene.get("cameras")
    if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS):
        raise ValueError("four reviewed original cameras required")
    for name in CAMERAS:
        camera = cameras[name]
        if camera.get("dimensions") != list(DIMENSIONS[name]) or camera.get("mount") not in ("world", "ego"):
            raise ValueError("reviewed original camera profile differs: " + name)
        pose = camera.get("pose")
        if not isinstance(pose, dict) or set(pose) != {"x", "y", "z", "pitch", "yaw", "roll"}:
            raise ValueError("reviewed six-axis camera pose required: " + name)
        if any(type(value) not in (int, float) or not math.isfinite(value) for value in pose.values()):
            raise ValueError("nonfinite original camera pose: " + name)
    return scene, {"opendrive": live_map.encode(), "device_inventory": sources["device_inventory"],
                   "highway_identity": sources["highway_identity"]}


def _camera_transform(carla, pose: dict):
    return carla.Transform(
        carla.Location(x=pose["x"], y=pose["y"], z=pose["z"]),
        carla.Rotation(pitch=pose["pitch"], yaw=pose["yaw"], roll=pose["roll"]))


def _body(actor) -> list[list[float]]:
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    if len(vertices) != 8:
        raise ValueError("original vehicle bounding box incomplete")
    bottom = sorted(vertices, key=lambda point: point.z)[:4]
    xy = [[float(point.x), float(point.y)] for point in bottom]
    if any(not all(math.isfinite(v) for v in point) for point in xy):
        raise ValueError("nonfinite original vehicle body")
    return xy


def _actor_sample(world, actor):
    location = actor.get_location()
    waypoint = world.get_map().get_waypoint(location, project_to_road=False)
    if waypoint is None:
        raise ValueError("original vehicle left mapped lane")
    return {"id": actor.id, "road_id": waypoint.road_id,
            "body_vertices_xy_m": _body(actor),
            "position_xyz_m": [location.x, location.y, location.z],
            "heading_deg": actor.get_transform().rotation.yaw,
            "speed_mps": math.sqrt(sum(getattr(actor.get_velocity(), axis) ** 2
                                       for axis in ("x", "y", "z")))}


def _control(carla, actor, route, point_index: int, request: str) -> int:
    if request == "brake":
        actor.apply_control(carla.VehicleControl(throttle=0.0, steer=0.0, brake=1.0))
        return point_index
    location = actor.get_location()
    if point_index < len(route) - 1 and math.hypot(
            route[point_index][0] - location.x, route[point_index][1] - location.y) < 3:
        point_index += 1
    target = route[point_index]
    if point_index == len(route) - 1 and math.hypot(
            target[0] - location.x, target[1] - location.y) < 3:
        actor.apply_control(carla.VehicleControl(throttle=0.0, steer=0.0, brake=1.0))
        return point_index
    desired = math.atan2(target[1] - location.y, target[0] - location.x)
    actual = math.radians(actor.get_transform().rotation.yaw)
    error = math.atan2(math.sin(desired - actual), math.cos(desired - actual))
    velocity = actor.get_velocity()
    speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
    actor.apply_control(carla.VehicleControl(
        throttle=max(0.0, min(.55, .25 * (8.0 - speed))),
        steer=max(-1.0, min(1.0, error / .5)),
        brake=max(0.0, min(.8, .2 * (speed - 8.0)))))
    return point_index


def run(world, carla, packet_path: Path, output: Path, response_mode: str,
        frame_count: int = 900) -> dict:
    if response_mode not in ("yield_before_entry", "advance_before_other_exit"):
        raise ValueError("unknown selected ego response")
    if frame_count != 900:
        raise ValueError("original acquisition requires 900 frames")
    output = Path(output)
    if output.exists() and not output.is_dir():
        raise ValueError("original output must be a directory")
    if any((output / name).exists() for name in (
            "native_trace.json", "source-manifest.json", "capture-scratch", "result.json")):
        raise ValueError("original output already contains a capture")
    scene, original_sources = reviewed_packet(
        packet_path, world, lambda x, y: carla.Location(x=x, y=y, z=0.0))
    expected_case = ("precedence" if response_mode == "yield_before_entry" else "advance")
    if scene.get("case_id") != "testing__C125697__NRS-484B-250-1__motor_vehicle_driver__" + expected_case:
        raise ValueError("original packet does not match selected exact case")
    saved_settings = copy.copy(world.get_settings())
    target_settings = copy.copy(saved_settings)
    target_settings.synchronous_mode = True
    target_settings.fixed_delta_seconds = .05
    actors = {}
    sensors = []
    queues = {}
    failure = None
    receipt = None
    try:
        world.apply_settings(target_settings)
        observed = world.get_settings()
        if observed.synchronous_mode is not True or observed.fixed_delta_seconds != .05:
            raise ValueError("original 20 Hz world settings readback failed")
        actors, _ = median_opening.construct_native(
            world, scene, lambda x, y: carla.Location(x=x, y=y, z=0),
            world.get_blueprint_library(), lambda _: _signal_state(world, scene))
        for name in CAMERAS:
            spec = scene["cameras"][name]
            blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
            width, height = DIMENSIONS[name]
            for key, value in (("image_size_x", width), ("image_size_y", height),
                               ("sensor_tick", .05), ("fov", 90)):
                blueprint.set_attribute(key, str(value))
            sensor = world.spawn_actor(
                blueprint, _camera_transform(carla, spec["pose"]),
                attach_to=actors["ego"] if spec["mount"] == "ego" else None)
            if sensor is None:
                raise ValueError("original camera spawn failed: " + name)
            sensors.append(sensor)
            queues[name] = Queue(maxsize=4)
            sensor.listen(queues[name].put_nowait)
        output.mkdir(parents=True, exist_ok=True)
        scratch = output / "capture-scratch"
        for name in CAMERAS:
            (scratch / name).mkdir(parents=True)
        frames = []
        maps = {name: [] for name in CAMERAS}
        indices = {"ego": 1, "other": 1}
        other_entered = False
        previous_other_inside = False
        ego_entered = False
        first_native_frame = None
        first_native_elapsed = None
        for index in range(frame_count):
            source_fresh = other_entered
            ego_request = median_opening.requested_ego_control(
                not ego_entered,
                previous_other_inside, source_fresh, response_mode)
            indices["ego"] = _control(carla, actors["ego"], scene["ego_route_xy_m"],
                                       indices["ego"], ego_request)
            indices["other"] = _control(carla, actors["other"], scene["other_route_xy_m"],
                                         indices["other"], "proceed")
            native_frame = world.tick()
            snapshot = world.get_snapshot()
            native_elapsed = float(snapshot.timestamp.elapsed_seconds)
            if native_frame != snapshot.frame:
                raise ValueError("original Native tick and snapshot frame differ")
            if first_native_frame is None:
                first_native_frame, first_native_elapsed = native_frame, native_elapsed
            if native_frame != first_native_frame + index or not math.isclose(
                    native_elapsed - first_native_elapsed, index / 20, abs_tol=.002):
                raise ValueError("original Native frame/clock discontinuity")
            readback = _signal_state(world, scene)
            ego, other = (_actor_sample(world, actors[name]) for name in ("ego", "other"))
            previous_other_inside = median_opening._rect_overlap(
                other["body_vertices_xy_m"], scene["crossing"]["bounds_xy_m"])
            other_entered = other_entered or previous_other_inside
            ego_entered = ego_entered or median_opening._rect_overlap(
                ego["body_vertices_xy_m"], scene["crossing"]["bounds_xy_m"])
            frames.append({"frame": index, "time_s": index / 20,
                           "native_frame_id": native_frame,
                           "native_elapsed_seconds": native_elapsed,
                           "signal_readback": readback, "ego": ego, "other": other})
            for name in CAMERAS:
                try:
                    image = queues[name].get(timeout=5)
                except Empty as error:
                    raise ValueError("original camera callback missing: " + name) from error
                width, height = DIMENSIONS[name]
                if image.frame != native_frame or image.width != width or image.height != height or abs(
                        float(image.timestamp) - native_elapsed) > .001:
                    raise ValueError("original camera frame/time/dimensions differ: " + name)
                raw = bytes(image.raw_data)
                if len(raw) != width * height * 4:
                    raise ValueError("original camera BGRA bytes incomplete: " + name)
                rgb = Image.frombytes("RGBA", (width, height), raw, "raw", "BGRA").convert("RGB")
                rgb.save(scratch / name / f"{index:06d}.png", format="PNG")
                maps[name].append({"video_frame": index, "carla_frame": native_frame,
                                   "time_s": native_elapsed})
        trace = {"case_id": scene["case_id"],
                 "map_sha256": scene["crossing"]["opendrive_sha256"],
                 "actor_ids": {name: actor.id for name, actor in actors.items()},
                 "frames": frames}
        observation = median_opening.measure_saved(trace, scene)
        (output / "native_trace.json").write_text(json.dumps(trace) + "\n")
        (output / "trace.jsonl").write_text("".join(json.dumps({
            "frame": row["native_frame_id"], "time_s": row["native_elapsed_seconds"],
            "position": {"x": row["ego"]["position_xyz_m"][0],
                         "y": row["ego"]["position_xyz_m"][1],
                         "z": row["ego"]["position_xyz_m"][2]},
            "heading_deg": row["ego"]["heading_deg"],
            "speed_mps": row["ego"]["speed_mps"]}) + "\n" for row in frames))
        (output / "video_frames.jsonl").write_text("".join(json.dumps({
            "video_frame": index, "carla_frame": row["native_frame_id"],
            "native_frame": row["native_frame_id"],
            "time_s": row["native_elapsed_seconds"]}) + "\n"
            for index, row in enumerate(frames)))
        (output / "scene.json").write_text(json.dumps(scene, indent=2) + "\n")
        (output / "opendrive.xodr").write_bytes(original_sources["opendrive"])
        (output / "device_inventory.json").write_bytes(original_sources["device_inventory"])
        (output / "highway_identity.json").write_bytes(original_sources["highway_identity"])
        for name in CAMERAS:
            (output / f"frame-map-{name}.json").write_text(json.dumps(maps[name]) + "\n")
            destination = output / f"{name}.mkv"
            process = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-framerate", "20", "-i", str(scratch / name / "%06d.png"),
                "-c:v", "ffv1", "-level", "3", str(destination)],
                capture_output=True, text=True)
            if process.returncode:
                raise ValueError("lossless original camera encoding failed: " + name + " " + process.stderr)
        shutil.rmtree(scratch)
        refs = {
            "native_trace": "native_trace.json", "opendrive": "opendrive.xodr",
            "device_inventory": "device_inventory.json",
            **{f"camera_{name}": f"{name}.mkv" for name in CAMERAS},
        }
        source_manifest = {"case_id": scene["case_id"], "frame_count": frame_count,
                           "sources": {name: {"path": path,
                                                "sha256": _sha((output / path).read_bytes())}
                                       for name, path in refs.items()}}
        manifest_bytes = (json.dumps(source_manifest, indent=2) + "\n").encode()
        (output / "source-manifest.json").write_bytes(manifest_bytes)
        (output / "original-source-manifest.json").write_bytes(manifest_bytes)
        receipt = {"case_id": scene["case_id"], "status": "original_capture_saved",
                   "requested_ego_response": response_mode, "observations": observation,
                   "source_manifest_sha256": _sha((output / "source-manifest.json").read_bytes()),
                   "physical_pixels_reviewed": False, "legal_judgment": "unresolved"}
        (output / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")
        (output / "acquisition-provenance.json").write_text(json.dumps({
            "provenance_kind": "native", "diagnostic_fixture": False,
            "physical_acceptance_claimed": False}) + "\n")
    except BaseException as error:
        failure = error
    finally:
        cleanup_errors = []
        for sensor in reversed(sensors):
            try:
                sensor.stop()
                sensor.destroy()
            except BaseException as error:
                cleanup_errors.append("camera release: " + str(error))
        for actor in reversed(tuple(actors.values())):
            try:
                actor.destroy()
            except BaseException as error:
                cleanup_errors.append("vehicle release: " + str(error))
        try:
            world.apply_settings(saved_settings)
            restored = world.get_settings()
            if (restored.synchronous_mode != saved_settings.synchronous_mode or
                    restored.fixed_delta_seconds != saved_settings.fixed_delta_seconds):
                cleanup_errors.append("world settings restoration readback failed")
        except BaseException as error:
            cleanup_errors.append("world settings restore: " + str(error))
    if cleanup_errors:
        if output.is_dir():
            (output / "native-run-status.json").write_text(json.dumps({
                "errors": cleanup_errors + ([str(failure)] if failure else []),
                "restoration_verified": False}) + "\n")
        raise RuntimeError("; ".join(cleanup_errors)) from failure
    if failure is not None:
        if output.is_dir():
            (output / "native-run-status.json").write_text(json.dumps({
                "errors": [str(failure)], "restoration_verified": True}) + "\n")
        raise failure
    if receipt is not None:
        if not (output / "construction.json").is_file() or not (output / "runner.py").is_file():
            raise ValueError("materialized Native construction revision missing")
        hashes = {str(path.relative_to(output)): _sha(path.read_bytes())
                  for path in sorted(output.rglob("*")) if path.is_file()}
        seal = {"format": "worker-sealed-capture", "provenance_kind": "native",
                "diagnostic_fixture": False, "frames": frame_count,
                "restoration": {"restored": True, "world_settings_readback": True},
                "encoder_exit_codes": {name: 0 for name in CAMERAS},
                "sources": hashes,
                "native_revision": {
                    "construction_sha256": _sha((output / "construction.json").read_bytes()),
                    "runner_sha256": _sha((output / "runner.py").read_bytes())},
                "events": ["capture_finished", "encoders_closed", "restoration_verified"],
                "source_digest": _sha(json.dumps(hashes, sort_keys=True).encode()),
                "physical_acceptance_claimed": False}
        (output / "capture-seal.json").write_text(json.dumps(seal, indent=2) + "\n")
    return receipt


def _signal_state(world, scene):
    actor_id = scene["governing_signal"]["actor_id"]
    signal = world.get_actors().find(actor_id)
    if signal is None or not str(signal.get_state()).lower().endswith("off"):
        raise ValueError("live governing signal is not inoperative")
    return "inoperative"
