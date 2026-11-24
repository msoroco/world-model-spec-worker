"""Unselected C229398 Native parking request; CPU --check never imports CARLA.

The selected operator must establish a qualifying nonmotor device separately.
The CARLA crossbike blueprint is only a motion/camera stand-in request.
"""

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VIEWS = ("overview", "approach", "curb", "device")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def request(frame, config):
    if not isinstance(frame, int) or frame < 0 or frame >= config["capture_frames"]:
        raise ValueError("Frame outside exact capture contract")
    return {
        "frame": frame,
        "phase": "approach" if frame < config["approach_frames"] else "stationary_request",
        "target_speed_mps": 2.0 if frame < config["approach_frames"] else 0.0,
        "handbrake_request": frame >= config["approach_frames"],
        "observed_native_motion": False,
    }


def check():
    cfg = json.loads((ROOT / "config.json").read_text())
    assert cfg["status"] == "unselected_native_request"
    assert cfg["rate_hz"] == 20 and cfg["capture_frames"] == 36043
    assert cfg["approach_frames"] == 40
    assert cfg["duration_s"] == 36043 / 20
    assert [row["name"] for row in cfg["cameras"]] == list(VIEWS)
    assert cfg["device_classification"] == "unresolved"
    assert cfg["road_sha256"] == sha(ROOT / "parking-road.xodr")
    assert request(39, cfg)["phase"] == "approach"
    assert request(40, cfg)["phase"] == "stationary_request"
    assert request(36042, cfg)["handbrake_request"] is True
    return {"passed": True, "case_id": cfg["case_id"], "frames": cfg["capture_frames"],
            "four_cameras": list(VIEWS), "physical_or_legal_acceptance": False}


def run_native(host, port, output):
    """Capture original Native pose and four camera streams if explicitly launched.

    This is an unselected prototype. Its blueprint alone cannot establish
    nonmotor classification, city jurisdiction, or parking activity.
    """
    import carla
    import queue

    cfg = json.loads((ROOT / "config.json").read_text())
    check()
    client = carla.Client(host, port)
    client.set_timeout(30)
    world = client.generate_opendrive_world((ROOT / "parking-road.xodr").read_text())
    settings = world.get_settings()
    previous_sync, previous_step = settings.synchronous_mode, settings.fixed_delta_seconds
    actor = None
    cameras = []
    incoming = queue.Queue()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    try:
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        library = world.get_blueprint_library()
        blueprint = library.find(cfg["prototype_blueprint"])
        actor = world.try_spawn_actor(blueprint, carla.Transform(carla.Location(x=5, y=-1.75, z=1), carla.Rotation(yaw=0)))
        if actor is None:
            raise RuntimeError("Crossbike prototype actor spawn failed")
        for view in cfg["cameras"]:
            bp = library.find("sensor.camera.rgb")
            bp.set_attribute("image_size_x", str(view["width"]))
            bp.set_attribute("image_size_y", str(view["height"]))
            bp.set_attribute("fov", str(view["fov_deg"]))
            pose = carla.Transform(carla.Location(*view["location_xyz_m"]), carla.Rotation(pitch=view["pitch_deg"]))
            sensor = world.spawn_actor(bp, pose, attach_to=actor)
            sensor.listen(lambda image, name=view["name"]: incoming.put((name, image)))
            cameras.append(sensor)
            (output / view["name"]).mkdir()
        with (output / "native-actor-frames.jsonl").open("x") as trace:
            for frame in range(cfg["capture_frames"]):
                target = request(frame, cfg)
                actor.apply_control(carla.VehicleControl(throttle=0.2 if target["phase"] == "approach" else 0.0,
                                                         brake=1.0 if target["handbrake_request"] else 0.0,
                                                         hand_brake=target["handbrake_request"]))
                native_frame = world.tick()
                pose = actor.get_transform()
                velocity = actor.get_velocity()
                trace.write(json.dumps({"frame": frame, "native_frame": native_frame,
                    "center_xyz_m": [pose.location.x, pose.location.y, pose.location.z],
                    "velocity_xyz_mps": [velocity.x, velocity.y, velocity.z],
                    "source_kind": "original_native_actor"}) + "\n")
                received = {}
                while len(received) < len(VIEWS):
                    name, image = incoming.get(timeout=30)
                    if image.frame == native_frame:
                        if name in received:
                            raise RuntimeError("Duplicate source camera frame")
                        image.save_to_disk(str(output / name / f"{frame:06d}.png"))
                        received[name] = image.frame
                if set(received) != set(VIEWS):
                    raise RuntimeError("Missing original camera frame")
    finally:
        for sensor in cameras:
            sensor.stop()
            sensor.destroy()
        if actor is not None:
            actor.destroy()
        settings.synchronous_mode, settings.fixed_delta_seconds = previous_sync, previous_step
        world.apply_settings(settings)


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
