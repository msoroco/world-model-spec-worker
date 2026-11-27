"""Survey-gated Native signed-road riding capture; --check is CPU only."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess


HERE = Path(__file__).resolve().parent
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
FRAMES = 600


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def config_check():
    cfg = json.loads((HERE / "config.json").read_text())
    if (cfg.get("rate_hz") != 20 or cfg.get("duration_s") != 30 or
            cfg.get("capture_frames") != FRAMES or cfg.get("road_sha256") != digest(HERE / "signed-road.xodr") or
            [item.get("name") for item in cfg.get("cameras", [])] != list(CAMERAS) or
            [(item.get("width"), item.get("height")) for item in cfg["cameras"]] !=
            [(1920, 1080), (1280, 720), (1280, 720), (1280, 720)] or
            cfg.get("case_id") != cfg.get("selected_case_id") or
            cfg.get("case_id") not in cfg.get("supported_case_ids", [])):
        raise ValueError("Exact signed-road capture contract differs")
    if cfg.get("route_kind") not in ("outside", "enter") or cfg.get("candidate_id") not in ("primary", "fallback1"):
        raise ValueError("Signed-road route or candidate differs")
    return cfg


def request(frame, cfg):
    if not isinstance(frame, int) or not 0 <= frame < FRAMES:
        raise ValueError("Frame outside capture")
    return {"target_speed_mps": cfg["target_speed_mps"],
            "requested_x_m": cfg["start_x_m"] + frame * cfg["target_speed_mps"] / 20,
            "observed_motion": False}


def survey_check(survey, cfg):
    required = ("map_or_road_review", "device_blueprint", "device_subtype",
                "sign_blueprint", "sign_transform", "sign_text_source",
                "sign_governed_interval_source", "director_determination_source",
                "roadway_access_source", "camera_world_transforms")
    if any(not survey.get(key) for key in required):
        raise ValueError("Reviewed sign, actor or roadway survey missing")
    if survey["device_subtype"] not in ("bicycle", "electric_bicycle", "electric_scooter"):
        raise ValueError("Covered machine source missing")
    if set(survey["camera_world_transforms"]) != set(CAMERAS):
        raise ValueError("Four surveyed cameras missing")
    if survey.get("governed_x_interval_m") != [40, 60]:
        raise ValueError("Sign-governed road interval changed")
    if survey.get("sign_message") != "NO BICYCLES, E-BICYCLES OR E-SCOOTERS":
        raise ValueError("Prohibition sign message differs")
    if survey.get("street_y_m") != cfg["street_y_m"]:
        raise ValueError("Roadway centerline differs")
    return survey


def transform(carla, pose):
    xyz = pose["xyz_m"]
    angles = pose["rotation_deg"]
    return carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                           carla.Rotation(pitch=angles[0], yaw=angles[1], roll=angles[2]))


def run_native(output, host, port, survey_path):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    cfg = config_check()
    survey = survey_check(json.loads(Path(survey_path).read_text()), cfg)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("Use an empty original attempt directory")
    client = carla.Client(host, port)
    client.set_timeout(120)
    previous = snapshot(client)
    source_world = client.get_world()
    if source_world.get_settings().synchronous_mode or any(
            actor.type_id.startswith(("vehicle.", "walker.", "sensor.", "controller."))
            for actor in source_world.get_actors()):
        raise RuntimeError("Exclusive idle Native world required")
    actors = []
    encoders = {}
    capture = None
    generated = False
    finished = False
    codes = {}
    try:
        world = client.generate_opendrive_world((HERE / "signed-road.xodr").read_text())
        generated = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        lib = world.get_blueprint_library()
        sign = world.try_spawn_actor(lib.find(survey["sign_blueprint"]),
                                     transform(carla, survey["sign_transform"]))
        if sign is None:
            raise RuntimeError("Surveyed physical prohibition sign spawn failed")
        actors.append(sign)
        device = world.try_spawn_actor(lib.find(survey["device_blueprint"]),
            carla.Transform(carla.Location(x=cfg["start_x_m"], y=cfg["street_y_m"], z=1),
                            carla.Rotation(yaw=0)))
        if device is None:
            raise RuntimeError("Surveyed cycle/scooter spawn failed")
        actors.append(device)
        cameras = {}
        for spec in cfg["cameras"]:
            bp = lib.find("sensor.camera.rgb")
            bp.set_attribute("image_size_x", str(spec["width"]))
            bp.set_attribute("image_size_y", str(spec["height"]))
            bp.set_attribute("fov", str(spec["fov_deg"]))
            bp.set_attribute("sensor_tick", "0.05")
            sensor = world.spawn_actor(bp, transform(carla, survey["camera_world_transforms"][spec["name"]]))
            actors.append(sensor)
            incoming = queue.Queue()
            sensor.listen(incoming.put)
            cameras[spec["name"]] = incoming
            encoders[spec["name"]] = subprocess.Popen([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                "-f", "rawvideo", "-pix_fmt", "bgra", "-s",
                f"{spec['width']}x{spec['height']}", "-r", "20", "-i", "-",
                "-frames:v", str(FRAMES), "-c:v", "ffv1",
                str(output / (spec["name"] + ".mkv"))], stdin=subprocess.PIPE,
                stderr=subprocess.PIPE)
        capture = PipelineCapture(client, device, output, cfg["case_id"],
                                  required_observations=cfg.get("required_atoms", []))
        rows = []
        first_elapsed = None
        with FrameMap(output / "video_frames.jsonl") as frame_map:
            for frame in range(FRAMES):
                target = request(frame, cfg)
                device.set_target_velocity(carla.Vector3D(x=target["target_speed_mps"], y=0, z=0))
                native = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native:
                    raise RuntimeError("Native world frame differs")
                if first_elapsed is None:
                    first_elapsed = snap.timestamp.elapsed_seconds
                pose = device.get_transform()
                speed = device.get_velocity()
                image_frames = {}
                for name, incoming in cameras.items():
                    image = incoming.get(timeout=60)
                    while image.frame < native:
                        image = incoming.get(timeout=60)
                    if image.frame != native:
                        raise RuntimeError("Four camera Native frame join differs")
                    encoders[name].stdin.write(image.raw_data)
                    image_frames[name] = image.frame
                frame_map.append(native, snap.timestamp.elapsed_seconds - first_elapsed,
                                 camera_native_frames=image_frames)
                capture.capture(native, snap.timestamp.elapsed_seconds - first_elapsed,
                                extra={"sign_actor_id": sign.id,
                                       "requested_x_m": target["requested_x_m"]})
                rows.append({"frame": frame,
                             "elapsed_s": snap.timestamp.elapsed_seconds - first_elapsed,
                             "camera_ids": list(CAMERAS), "native_frame": native,
                             "actor_id": device.id, "sign_actor_id": sign.id,
                             "actor_x_m": pose.location.x,
                             "actor_speed_mps": math.sqrt(speed.x**2 + speed.y**2 + speed.z**2),
                             "riding_machine": True})
        (output / "raw-frames.json").write_text(json.dumps(rows, separators=(",", ":")) + "\n")
        for name, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            codes[name] = process.wait(timeout=300)
            if codes[name]:
                raise RuntimeError("Camera encoding failed: " + name + error.decode()[-300:])
        capture.close(confirmed=True)
        capture = None
        (output / "setup.template.json").write_text(json.dumps({
            "case_id": cfg["case_id"], "source_kind": "original_native_review",
            "actor_kind": survey["device_subtype"], "surface_kind": "roadway",
            "prohibition_sign_erected": True, "sign_prohibits_actor": True,
            "governed_x_interval_m": [40, 60], "sign_pixels_verified": False,
            "administrative_authority_verified": False,
            "source_files": {"sign_pixels": None, "director_determination": None,
                             "roadway_access": None},
            "review_note": "Original sign pixels and authority sources must be reviewed, hashed and staged as setup.json."}, indent=2) + "\n")
        finished = True
    finally:
        if capture is not None:
            capture.close(confirmed=False)
        for process in encoders.values():
            if process.poll() is None:
                process.kill()
                process.wait()
        for actor in reversed(actors):
            try:
                if hasattr(actor, "stop"):
                    actor.stop()
                actor.destroy()
            except Exception:
                pass
        if generated:
            restored = restore(client, previous)
            if finished and len(codes) == len(CAMERAS):
                seal_capture(output, frames=FRAMES, restoration=restored,
                             errors=[], encoder_exit_codes=codes,
                             context={"case_id": cfg["case_id"], "sign_actor_id": sign.id})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--survey")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    if args.check:
        print(json.dumps(config_check()))
    elif args.survey and args.output_dir:
        run_native(args.output_dir, args.host, args.port, args.survey)
    else:
        parser.error("Use --check or provide --survey and --output-dir")


if __name__ == "__main__":
    main()
