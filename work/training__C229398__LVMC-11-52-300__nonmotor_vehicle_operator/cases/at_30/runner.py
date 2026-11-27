"""Exact C229398 Native parking request; CPU --check never imports CARLA.

The operator must establish a qualifying nonmotor device from reviewed sources.
The CARLA bicycle blueprint is a motion/camera stand-in, not a legal finding.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from duration_policy import TOTAL_FRAMES, request as duration_request, stop_frame
from source_gate import audit as audit_source


ROOT = Path(__file__).resolve().parent
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def request(frame, config):
    target = duration_request(config["case_id"], frame)
    if config["parking_stop_frame"] != stop_frame(config["case_id"]):
        raise ValueError("Exact duration request differs")
    return dict(target, handbrake_request=target["brake_request"],
                observed_native_motion=False)


def check():
    cfg = json.loads((ROOT / "config.json").read_text())
    assert cfg["status"] == "selected_cpu_draft"
    assert cfg["rate_hz"] == 20 and cfg["capture_frames"] == TOTAL_FRAMES
    assert cfg["parking_stop_frame"] == stop_frame(cfg["case_id"])
    assert cfg["duration_s"] == TOTAL_FRAMES / 20
    assert [row["name"] for row in cfg["cameras"]] == list(VIEWS)
    assert cfg["device_classification"] == "unresolved"
    assert cfg["road_sha256"] == sha(ROOT / "parking-road.xodr")
    assert request(cfg["parking_stop_frame"] - 1, cfg)["phase"] == "approach"
    assert request(cfg["parking_stop_frame"], cfg)["phase"] == "parking_request"
    assert request(TOTAL_FRAMES - 1, cfg)["handbrake_request"] is True
    return {"passed": True, "case_id": cfg["case_id"], "frames": cfg["capture_frames"],
            "four_cameras": list(VIEWS), "physical_or_legal_acceptance": False}


def run_native(host, port, output):
    """Capture one original, source-reviewed 20 Hz parking request.

    Original motion and pixels are checked after capture. The bicycle blueprint
    does not establish legal classification or jurisdiction by itself.
    """
    import carla
    import queue
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    cfg = json.loads((ROOT / "config.json").read_text())
    check()
    context = os.environ.get("C229398_CONTEXT_PACKET")
    if not context:
        raise ValueError("Original qualifying source review packet required")
    source_result = audit_source(context, require_original=True)
    if source_result["case_id"] != cfg["case_id"] or not source_result[
            "qualifying_context_supported"]:
        raise ValueError("Original qualifying source review did not match case")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(context, output / "review-source.json")
    packet = json.loads(Path(context).read_text())
    for item in packet["sources"].values():
        relative = Path(item["path"])
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(context).resolve().parent / relative, target)
    if audit_source(output / "review-source.json", require_original=True)[
            "packet_sha256"] != source_result["packet_sha256"]:
        raise ValueError("Original context changed during staging")
    client = carla.Client(host, port)
    client.set_timeout(180)
    source_world = client.get_world()
    saved = snapshot(client)
    if source_world.get_settings().synchronous_mode or any(
            actor.type_id.startswith(("vehicle.", "walker.", "sensor.", "controller."))
            for actor in source_world.get_actors()):
        raise RuntimeError("Exclusive idle asynchronous Native world required")
    actors = []
    encoders = {}
    camera_queues = {}
    capture = None
    changed = False
    closed_encoders = {}
    finished = False
    try:
        world = client.generate_opendrive_world((ROOT / "parking-road.xodr").read_text())
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        settings.substepping = True
        settings.max_substep_delta_time = 0.01
        settings.max_substeps = 10
        world.apply_settings(settings)
        weather = world.get_weather()
        weather.sun_altitude_angle = -20
        weather.precipitation = 0
        weather.fog_density = 0
        world.set_weather(weather)
        waypoint = world.get_map().get_waypoint(
            carla.Location(x=40, y=-3.0, z=1), project_to_road=True,
            lane_type=carla.LaneType.Driving)
        if waypoint is None or waypoint.road_id != 1:
            raise RuntimeError("Original street target readback differs")
        library = world.get_blueprint_library()
        blueprint = library.find(cfg["prototype_blueprint"])
        subject = world.try_spawn_actor(blueprint, carla.Transform(
            carla.Location(x=35, y=-3.0, z=1), carla.Rotation(yaw=0)))
        if subject is None:
            raise RuntimeError("Bicycle prototype actor spawn failed")
        actors.append(subject)
        for view in cfg["cameras"]:
            bp = library.find("sensor.camera.rgb")
            bp.set_attribute("image_size_x", str(view["width"]))
            bp.set_attribute("image_size_y", str(view["height"]))
            bp.set_attribute("fov", str(view["fov_deg"]))
            bp.set_attribute("sensor_tick", "0.05")
            xyz = view["location_xyz_m"]
            pose = carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                                   carla.Rotation(pitch=view["pitch_deg"]))
            sensor = world.spawn_actor(bp, pose)
            actors.append(sensor)
            received = queue.Queue()
            sensor.listen(received.put)
            camera_queues[view["name"]] = received
            encoders[view["name"]] = subprocess.Popen([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                "-f", "rawvideo", "-pix_fmt", "bgra",
                "-s", f"{view['width']}x{view['height']}", "-r", "20", "-i", "-",
                "-frames:v", str(cfg["capture_frames"]), "-c:v", "ffv1",
                str(output / (view["name"] + ".mkv"))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        capture = PipelineCapture(client, subject, output, cfg["case_id"],
                                  required_observations=[])
        with (output / "native-actor-frames.jsonl").open("x") as trace, FrameMap(
                output / "video_frames.jsonl") as frame_map:
            for frame in range(cfg["capture_frames"]):
                target = request(frame, cfg)
                subject.set_target_velocity(carla.Vector3D(x=target["target_speed_mps"], y=0, z=0))
                subject.apply_control(carla.VehicleControl(throttle=0.2 if target["phase"] == "approach" else 0.0,
                                                         brake=1.0 if target["handbrake_request"] else 0.0,
                                                         hand_brake=target["handbrake_request"]))
                native_frame = world.tick()
                pose = subject.get_transform()
                velocity = subject.get_velocity()
                trace.write(json.dumps({"frame": frame, "native_frame": native_frame,
                    "center_xyz_m": [pose.location.x, pose.location.y, pose.location.z],
                    "velocity_xyz_mps": [velocity.x, velocity.y, velocity.z],
                    "requested_phase": target["phase"],
                    "source_kind": "original_native_actor"}) + "\n")
                capture.capture(native_frame, frame / 20,
                                extra={"night_parking_requested_phase": target["phase"]})
                received = {}
                for name, incoming in camera_queues.items():
                    image = incoming.get(timeout=60)
                    while image.frame < native_frame:
                        image = incoming.get(timeout=60)
                    if image.frame != native_frame:
                        raise RuntimeError("Original camera frame join differs")
                    encoders[name].stdin.write(image.raw_data)
                    received[name] = image.frame
                if set(received) != set(VIEWS):
                    raise RuntimeError("Missing original camera frame")
                frame_map.append(native_frame, frame / 20,
                                 camera_native_frames=received)
        for name, encoder in encoders.items():
            encoder.stdin.close()
            error = encoder.stderr.read()
            closed_encoders[name] = encoder.wait(timeout=300)
            if closed_encoders[name] or not (output / (name + ".mkv")).is_file():
                raise RuntimeError("Camera encoding failed: " + name + error.decode()[-300:])
        capture.close(confirmed=True)
        capture = None
        (output / "street-geometry.json").write_text(json.dumps({
            "street_bounds_xy_m": [0.0, 100.0, -3.5, 3.5],
            "native_target_road_id": waypoint.road_id,
            "native_target_lane_id": waypoint.lane_id,
            "source_kind": "original_native", "law_jurisdiction_review_sha256":
            source_result["packet_sha256"]}, sort_keys=True) + "\n")
        finished = True
    finally:
        if capture is not None:
            capture.close(confirmed=False)
        for encoder in encoders.values():
            if encoder.poll() is None:
                encoder.kill()
                encoder.wait()
        for actor in reversed(actors):
            try:
                if hasattr(actor, "stop"):
                    actor.stop()
                actor.destroy()
            except Exception:
                pass
        if changed:
            restored = restore(client, saved)
            if finished and len(closed_encoders) == len(VIEWS):
                seal_capture(output, frames=cfg["capture_frames"], restoration=restored,
                             errors=[], encoder_exit_codes=closed_encoders,
                             context={"case_id": cfg["case_id"],
                                      "source_review_sha256": source_result["packet_sha256"]})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check()))
    elif args.output_dir:
        run_native(args.host, args.port, args.output_dir)
    else:
        parser.error("Use --check or --output-dir")


if __name__ == "__main__":
    main()
