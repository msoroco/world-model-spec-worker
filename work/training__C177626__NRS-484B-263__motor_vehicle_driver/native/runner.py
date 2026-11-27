"""Native controlled-access entry acquisition draft for exact C177626 cases.

Run only against an exclusively owned, idle CARLA world. The runner writes
original actors, four source cameras and a PipelineCapture under .runtime-work.
It makes no controlled-access designation or legal hazard finding.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from math import atan2, degrees, hypot, pi
import os
from pathlib import Path
import queue
import subprocess
import traceback

from acquisition import VIEWS, bind_original
from controlled_access_yield import FRAME_COUNT, FRAME_RATE, POLICY_GAP_S, control_request
from geometry import RAMP_HEADING, open_drive, route_points, validate_topology


ASSIGNMENT = "training__C177626__NRS-484B-263__motor_vehicle_driver"
CASE_PREFIX = ASSIGNMENT + "__selected_ed45c8e4__condition_"
CANDIDATES = {
    "near_70": {"near_x_m": -70.0, "far_x_m": -130.0, "through_speed_mps": 8.0},
    "near_80": {"near_x_m": -80.0, "far_x_m": -135.0, "through_speed_mps": 8.0},
    "near_90": {"near_x_m": -90.0, "far_x_m": -140.0, "through_speed_mps": 8.0},
    "near_100": {"near_x_m": -100.0, "far_x_m": -145.0, "through_speed_mps": 8.0},
}


def cameras() -> list[dict]:
    return [
        {"name": "overview", "width": 1920, "height": 1080, "fov_deg": 100,
         "xyz_m": [0, 0, 60], "pitch_deg": -90, "yaw_deg": 0},
        {"name": "approach", "width": 1280, "height": 720, "fov_deg": 95,
         "xyz_m": [2, 0, 4], "pitch_deg": -8, "yaw_deg": 0},
        {"name": "reference_corner", "width": 1280, "height": 720, "fov_deg": 95,
         "xyz_m": [-5, 4, 8], "pitch_deg": -15, "yaw_deg": 145},
        {"name": "driver_reference", "width": 1280, "height": 720, "fov_deg": 90,
         "xyz_m": [0.5, 0.2, 1.7], "pitch_deg": 0, "yaw_deg": 0},
    ]


def check(case_id: str, candidate_id: str) -> dict:
    if case_id not in (CASE_PREFIX + "a", CASE_PREFIX + "b"):
        raise ValueError("exact selected entry case required")
    if candidate_id not in CANDIDATES:
        raise ValueError("one of four distinct source candidates required")
    geometry = validate_topology(open_drive())
    if geometry["controlled_access_designation_verified"]:
        raise ValueError("authored geometry may not assert legal designation")
    return {"case_id": case_id, "candidate_id": candidate_id,
            "policy": "earlier_yield" if case_id.endswith("_a") else "later_yield",
            "duration_s": FRAME_COUNT / FRAME_RATE, "rate_hz": FRAME_RATE,
            "camera_views": list(VIEWS), "geometry": geometry,
            "native_original_present": False, "physical_success_claimed": False}


def _write_new(path: Path, data: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write("\n")


def _actor(actor, mapping) -> dict:
    pose = actor.get_transform()
    waypoint = mapping.get_waypoint(pose.location, project_to_road=False)
    if waypoint is None:
        raise RuntimeError("original actor left authored road")
    velocity = actor.get_velocity()
    box = actor.bounding_box
    return {
        "center_xy_m": [pose.location.x, pose.location.y],
        "velocity_xy_mps": [velocity.x, velocity.y],
        "radius_m": hypot(box.extent.x, box.extent.y),
        "road_id": waypoint.road_id, "lane_id": waypoint.lane_id,
        "yaw_deg": pose.rotation.yaw,
    }


def _joined_image(frame: int, spec: dict, source: queue.Queue,
                  encoder: subprocess.Popen, numpy_module) -> None:
    image = source.get(timeout=30)
    while image.frame < frame:
        image = source.get(timeout=30)
    if image.frame != frame:
        raise RuntimeError("original camera/Native frame join failed")
    rgba = numpy_module.frombuffer(image.raw_data, dtype=numpy_module.uint8)
    if rgba.size != spec["width"] * spec["height"] * 4:
        raise RuntimeError("original camera byte count differs")
    rgb = rgba.reshape(spec["height"], spec["width"], 4)[:, :, :3][:, :, ::-1]
    encoder.stdin.write(rgb.tobytes())


def _steer_to_route(actor, points: list[list[float]]) -> float:
    pose = actor.get_transform()
    x, y = pose.location.x, pose.location.y
    nearest = min(range(len(points)), key=lambda i: hypot(points[i][0] - x, points[i][1] - y))
    target = points[min(nearest + 20, len(points) - 1)]
    desired = atan2(target[1] - y, target[0] - x)
    current = pose.rotation.yaw * pi / 180
    delta = (desired - current + pi) % (2 * pi) - pi
    return max(-0.5, min(0.5, 0.7 * delta))


def execute(case_id: str, candidate_id: str, output: Path, host: str, port: int) -> None:
    proposal = check(case_id, candidate_id)
    output = output.resolve()
    scratch = next((parent for parent in output.parents if parent.name == ".runtime-work"), None)
    if scratch is None:
        raise ValueError("materialized output directory must be under .runtime-work")
    if output == scratch or scratch not in output.parents or not output.is_dir():
        raise ValueError("materialized output directory must be under .runtime-work")
    pipeline_root = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
    if not pipeline_root or scratch not in Path(pipeline_root).resolve().parents:
        raise ValueError("export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore
    client = carla.Client(host, port)
    client.set_timeout(180)
    prior = client.get_world()
    saved = snapshot(client)
    if saved["settings"].synchronous_mode or any(
        actor.type_id.startswith(("vehicle.", "walker.", "sensor."))
        for actor in prior.get_actors()
    ):
        raise RuntimeError("exclusive idle asynchronous Native world required")
    owned = []
    camera_queues: dict[str, queue.Queue] = {}
    encoders: dict[str, subprocess.Popen] = {}
    encoder_logs = {}
    encoder_exit_codes = {}
    capture = None
    changed = False
    error = None
    restored = None
    rows = []
    camera_rows = []
    try:
        world = client.generate_opendrive_world(open_drive())
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / FRAME_RATE
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping = world.get_map()
        map_hash = sha256(mapping.to_opendrive().encode()).hexdigest()
        blueprint = world.get_blueprint_library().find("vehicle.lincoln.mkz_2020")
        route = route_points("ego_entry")
        start = route[40]
        ego = world.spawn_actor(blueprint, carla.Transform(
            carla.Location(x=start[0], y=start[1], z=1.0),
            carla.Rotation(yaw=degrees(RAMP_HEADING))))
        owned.append(ego)
        profile = CANDIDATES[candidate_id]
        traffic = {}
        for name, x in (("near", profile["near_x_m"]), ("far", profile["far_x_m"])):
            actor = world.spawn_actor(blueprint, carla.Transform(
                carla.Location(x=x, y=-1.75, z=1.0)))
            owned.append(actor)
            traffic[name] = actor
        context = {
            "case_id": case_id, "candidate_id": candidate_id,
            "route_kind": "entry", "map_source": "native_opendrive_readback",
            "map_sha256": map_hash,
            "actor_inventory_source": "original_carla_actor_registry",
            "approaching_vehicle_ids": ["near", "far"],
            "controlled_access_designation_verified": False,
            "legal_immediate_hazard_conclusion": None,
            "legal_reasonable_safety_conclusion": None,
        }
        _write_new(output / "authored-context.json", context)
        for spec in cameras():
            camera_blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
            for key, value in (("image_size_x", spec["width"]),
                               ("image_size_y", spec["height"]),
                               ("fov", spec["fov_deg"]), ("sensor_tick", 0)):
                camera_blueprint.set_attribute(key, str(value))
            xyz = spec["xyz_m"]
            sensor = world.spawn_actor(camera_blueprint,
                carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                                carla.Rotation(pitch=spec["pitch_deg"], yaw=spec["yaw_deg"])),
                attach_to=ego)
            owned.append(sensor)
            source = queue.Queue()
            sensor.listen(source.put)
            camera_queues[spec["name"]] = source
            encoder_logs[spec["name"]] = (output / (spec["name"] + ".encoder.log")).open("x")
            encoders[spec["name"]] = subprocess.Popen([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                f"{spec['width']}x{spec['height']}", "-r", str(FRAME_RATE),
                "-i", "pipe:0", "-an", "-c:v", "ffv1", "-level", "1",
                str(output / (spec["name"] + ".mkv"))],
                stdin=subprocess.PIPE, stderr=encoder_logs[spec["name"]])
        capture = PipelineCapture(client, ego, output, case_id, required_observations=[])
        initial_time = world.get_snapshot().timestamp.elapsed_seconds
        with (output / "native_samples.jsonl").open("x", encoding="utf-8") as stream, \
             (output / "camera_frames.jsonl").open("x", encoding="utf-8") as camera_stream, \
             (output / "entry_history.jsonl").open("x", encoding="utf-8") as entry_stream, \
             FrameMap(output / "video_frames.jsonl") as frame_map:
            for index in range(FRAME_COUNT):
                for actor in traffic.values():
                    actor.set_target_velocity(carla.Vector3D(x=profile["through_speed_mps"]))
                previous = _actor(ego, mapping)
                ego_speed = hypot(*previous["velocity_xy_mps"])
                ego_arrival = max(0.0, -previous["center_xy_m"][0]) / max(ego_speed, 0.1)
                gaps = []
                for actor in traffic.values():
                    observed = _actor(actor, mapping)
                    speed = hypot(*observed["velocity_xy_mps"])
                    if observed["center_xy_m"][0] < 0 and speed > 0.1:
                        gaps.append(abs(ego_arrival + observed["center_xy_m"][0] / speed))
                request = control_request(proposal["policy"], min(gaps) if gaps else None)
                ego.apply_control(carla.VehicleControl(
                    throttle=request["throttle"], brake=request["brake"],
                    steer=_steer_to_route(ego, route)))
                native_frame = world.tick()
                elapsed = world.get_snapshot().timestamp.elapsed_seconds - initial_time
                sample = _actor(ego, mapping)
                observed_speed = hypot(*sample["velocity_xy_mps"])
                row = {"frame": index, "native_frame": native_frame,
                       "time_s": index / FRAME_RATE,
                       "native_elapsed_s": elapsed, "ego": sample,
                       "traffic": {name: _actor(actor, mapping)
                                   for name, actor in traffic.items()},
                       "ego_yielding": observed_speed < 2.0 and sample["center_xy_m"][0] < 0,
                       "controller_yield_request": request["yield_request"]}
                stream.write(json.dumps(row, allow_nan=False) + "\n")
                entry_stream.write(json.dumps({
                    "frame": native_frame, "time_s": elapsed,
                    "position_m": sample["center_xy_m"],
                    "road_id": sample["road_id"]}, allow_nan=False) + "\n")
                for spec in cameras():
                    _joined_image(native_frame, spec, camera_queues[spec["name"]],
                                  encoders[spec["name"]], np)
                joined = {"frame": native_frame,
                          "views": {view: native_frame for view in VIEWS}}
                camera_stream.write(json.dumps(joined, allow_nan=False) + "\n")
                capture.capture(native_frame, elapsed, extra={"c177626_native": row})
                frame_map.append(native_frame, elapsed)
                rows.append(row)
                camera_rows.append(joined)
        _write_new(output / "source-bound-measurements.json",
                   bind_original(rows, camera_rows, context, proposal["policy"]))
    except BaseException as exc:
        error = {"type": type(exc).__name__, "message": str(exc),
                 "traceback": traceback.format_exc()}
    finally:
        if capture is not None:
            try:
                capture.close(confirmed=error is None)
            except BaseException as exc:
                error = error or {"capture_close_error": str(exc)}
        for name, encoder in encoders.items():
            try:
                encoder.stdin.close()
                encoder_exit_codes[name] = encoder.wait(timeout=180)
                if encoder_exit_codes[name] != 0:
                    raise RuntimeError("lossless camera encoder failed: " + name)
            except BaseException as exc:
                error = error or {"encoder_error": str(exc)}
            encoder_logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith("sensor.") and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {"owned actor cleanup error": str(exc)}
        if changed:
            try:
                restored = restore(client, saved)
            except BaseException as exc:
                error = error or {"world restore error": str(exc)}
        _write_new(output / "native-draft-report.json", {
            "case_id": case_id, "candidate_id": candidate_id,
            "observed_frames": len(rows), "expected_frames": FRAME_COUNT,
            "world_restoration": restored, "error": error,
            "selected_delivery": False, "physical_success_claimed": False})
        if error is None and len(rows) == FRAME_COUNT:
            try:
                seal_capture(output, frames=FRAME_COUNT, restoration=restored,
                             errors=[], encoder_exit_codes=encoder_exit_codes,
                             context={"case_id": case_id, "candidate_id": candidate_id,
                                      "controlled_access_designation_verified": False})
            except BaseException as exc:
                error = {"capture_seal_error": str(exc)}
        if error is not None:
            _write_new(output / "native-run-status.json", {"errors": [error],
                       "case_id": case_id, "candidate_id": candidate_id})
    if error:
        raise RuntimeError("Native draft failed; inspect native-draft-report.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--candidate-id", choices=tuple(CANDIDATES), required=True)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check(args.case_id, args.candidate_id), allow_nan=False))
    else:
        if args.output_dir is None or args.host is None or args.port is None:
            raise ValueError("explicit owned Native endpoint and materialized output required")
        execute(args.case_id, args.candidate_id, args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
