"""Source-gated Native emergency move-over requests; no physical or legal verdict."""
import argparse
import hashlib
import json
import math
import queue
import subprocess
from pathlib import Path

from road_geometry import ADJACENT_LANE, EMERGENCY_LANE, NONADJACENT_LANE, check as check_road
from road_geometry import lane_centers, road_xml


AID = "training__C405647__NRS-484B-267-2b__motor_vehicle_driver"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
COUNT = 600
RATE = 20


def require(value, message):
    if not value:
        raise ValueError(message)


def check(config):
    case = config.get("case_id", "")
    require(case in {AID + "__probe_0" + str(i) for i in range(1, 6)}, "Unexpected case")
    require((config.get("law_id"), config.get("cell_id"), config.get("actor")) ==
            ("NRS-484B-267-2b", "C405647", "motor_vehicle_driver"), "Exact identity changed")
    require(config.get("frozen_cell") == {"layout": "road", "maneuver": "travel",
                                           "control": "emergency_vehicle"}, "Frozen cell changed")
    require((config.get("rate_hz"), config.get("duration_s"), config.get("frames")) ==
            (RATE, 30, COUNT), "Full capture interval changed")
    cameras = config.get("cameras", [])
    require([c.get("name") for c in cameras] == list(CAMERAS) and
            [(c.get("width"), c.get("height")) for c in cameras] ==
            [(1920, 1080), (1280, 720), (1280, 720), (1280, 720)] and
            all(c.get("pose_strategy") and c.get("fov_deg") for c in cameras),
            "Four-view profile changed")
    require(config.get("physical_acceptance_claimed") is False and
            config.get("legal_verdict") is None, "Unobserved outcome claimed")
    suffix = case[-2:]
    require(config.get("requested_response") ==
            ("slow_wide" if suffix == "01" else "fast_narrow" if suffix == "02" else "slow_wide"),
            "Requested response differs")
    require(config.get("requested_source_mode") ==
            ("visible_hand_signal" if suffix == "04" else "moving_vehicle"),
            "Emergency activation request differs")
    check_road()
    return {"case_id": case, "frames": COUNT, "cameras": list(CAMERAS),
            "carla_contacted": False, "physical_acceptance_claimed": False}


def _pose(carla, xyz, rotation=(0, 0, 0)):
    return carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                           carla.Rotation(pitch=rotation[0], yaw=rotation[1], roll=rotation[2]))


def _record(actor, mapping, carla):
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    waypoint = mapping.get_waypoint(transform.location, project_to_road=False,
                                    lane_type=carla.LaneType.Driving)
    extent = actor.bounding_box.extent
    return {"actor_id": actor.id, "x_m": transform.location.x,
            "y_m": transform.location.y, "z_m": transform.location.z,
            "velocity_xyz_mps": [velocity.x, velocity.y, velocity.z],
            "speed_mps": math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2),
            "lane_id": waypoint.lane_id if waypoint else None,
            "road_id": waypoint.road_id if waypoint else None,
            "half_length_m": extent.x, "half_width_m": extent.y}


def _camera_positions():
    return {"overview": ([-20, -5, 17], [-55, 0, 0]),
            "approach": ([-45, -4, 4], [-8, 0, 0]),
            "reference_corner": ([-20, -11, 7], [-20, 75, 0]),
            "driver_reference": ([-15, -5, 3], [-5, 180, 0])}


def requested_velocities(suffix, frame):
    """Engineering controls only; original lane occupancy must be read back."""
    require(suffix in {"01", "02", "03", "04", "05"}, "Unknown control case")
    require(0 <= frame < COUNT, "Frame outside capture")
    ego = (6.0 if suffix == "02" else 4.0, 0.0)
    emergency = (0.0 if suffix == "04" else 1.2, 0.0)
    traffic = None
    return {"ego": ego, "emergency": emergency, "traffic": traffic,
            "qualifying_approach_claimed": False, "lane_change_safe_claimed": False}


def execute(config, output, host, port):
    check(config)
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore
    from hand_signal_pose import apply_hand_signal, spawn_source_driver_proxy

    output = Path(output)
    require(output.is_dir() and not (output / "emergency-native.jsonl").exists() and
            not (output / "video_frames.jsonl").exists(),
            "Original output already exists or was not materialized")
    (output / "road.xodr").write_text(road_xml() + "\n")
    client = carla.Client(host, port)
    client.set_timeout(120)
    saved = snapshot(client)
    world = client.get_world()
    actors, encoders, cameras, writer = [], {}, {}, None
    restored, encoder_codes = None, {}
    case = config["case_id"]
    suffix = case[-2:]
    try:
        require(not saved["settings"].synchronous_mode, "Exclusive asynchronous world required")
        world = client.generate_opendrive_world(road_xml())
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE
        world.apply_settings(settings)
        mapping = world.get_map()
        lib = world.get_blueprint_library()
        ego_y = -4.55 if suffix == "02" else -5.95
        ego = world.try_spawn_actor(lib.find(config["ego_blueprint"]),
                                    _pose(carla, [-85, ego_y, 1]))
        emergency = world.try_spawn_actor(lib.find(config["emergency_blueprint"]),
                                          _pose(carla, [-20, lane_centers()[EMERGENCY_LANE], 1]))
        require(ego is not None and emergency is not None, "Native actor spawn failed")
        actors.extend((ego, emergency))
        for actor, lane in ((ego, ADJACENT_LANE), (emergency, EMERGENCY_LANE)):
            observed = _record(actor, mapping, carla)
            require(observed["lane_id"] == lane, "Authored lane Native readback differs")
        traffic = None
        signal_actor = None
        if suffix == "04":
            signal_actor = spawn_source_driver_proxy(carla, world, emergency,
                                                      config["signal_walker_blueprint"])
            actors.append(signal_actor)
            apply_hand_signal(carla, signal_actor)
        elif suffix == "05":
            officer_bp = lib.find(config["officer_walker_blueprint"])
            require(officer_bp is not None, "Reviewed officer blueprint unavailable")
            signal_actor = world.try_spawn_actor(
                officer_bp, _pose(carla, [-28, -11, 1], [0, 90, 0]))
            require(signal_actor is not None, "Officer direction actor spawn failed")
            actors.append(signal_actor)
            apply_hand_signal(carla, signal_actor)
        positions = _camera_positions()
        for item in config["cameras"]:
            name = item["name"]
            bp = lib.find("sensor.camera.rgb")
            bp.set_attribute("image_size_x", str(item["width"]))
            bp.set_attribute("image_size_y", str(item["height"]))
            bp.set_attribute("fov", str(item["fov_deg"]))
            bp.set_attribute("sensor_tick", str(1 / RATE))
            xyz, rotation = positions[name]
            camera = world.spawn_actor(bp, _pose(carla, xyz, rotation))
            actors.append(camera)
            q = queue.Queue()
            camera.listen(q.put)
            cameras[name] = q
            encoders[name] = subprocess.Popen(
                ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "rawvideo",
                 "-pix_fmt", "bgra", "-s", f"{item['width']}x{item['height']}",
                 "-r", str(RATE), "-i", "-", "-frames:v", str(COUNT),
                 "-c:v", "ffv1", str(output / (name + ".mkv"))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        writer = PipelineCapture(client, ego, output, case,
                                 required_observations=config.get("required_atoms", []))
        first = None
        with FrameMap(output / "video_frames.jsonl") as fmap, \
                (output / "emergency-native.jsonl").open("x") as stream:
            for i in range(COUNT):
                emergency.set_light_state(carla.VehicleLightState(
                    carla.VehicleLightState.Special1 if i // 10 % 2 == 0 else 0))
                controls = requested_velocities(suffix, i)
                emergency.set_target_velocity(carla.Vector3D(
                    x=controls["emergency"][0], y=0, z=0))
                ego.set_target_velocity(carla.Vector3D(
                    x=controls["ego"][0], y=controls["ego"][1], z=0))
                if traffic is not None:
                    traffic.set_target_velocity(carla.Vector3D(
                        x=controls["traffic"][0], y=0, z=0))
                native = world.tick()
                snap = world.get_snapshot()
                require(snap.frame == native, "Native frame mismatch")
                if first is None:
                    first = snap.timestamp.elapsed_seconds
                relative = snap.timestamp.elapsed_seconds - first
                writer.capture(native, relative, extra={"emergency_actor_id": emergency.id})
                camera_frames = {}
                for name, q in cameras.items():
                    image = q.get(timeout=30)
                    require(image.frame == native, "Camera frame mismatch")
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = image.frame
                fmap.append(native, relative, camera_native_frames=camera_frames)
                stream.write(json.dumps({"frame": i, "native_frame": native,
                    "t_s": relative, "source_kind": "original_native_observation",
                    "ego": _record(ego, mapping, carla),
                    "emergency": _record(emergency, mapping, carla),
                    "traffic": _record(traffic, mapping, carla) if traffic else None,
                    "weather_precipitation": world.get_weather().precipitation,
                    "weather_wetness": world.get_weather().wetness,
                    "road_obstruction_observed": False,
                    "emergency_light_state": int(emergency.get_light_state()),
                    "source_driver_hand_signal_requested": suffix == "04",
                    "officer_hand_direction_requested": suffix == "05",
                    "officer_direction_requested": suffix == "05",
                    "requested_ego_speed_mps": controls["ego"][0],
                    "requested_ego_lateral_start_m": ego_y}) + "\n")
        for name, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            encoder_codes[name] = process.wait(timeout=180)
            require(encoder_codes[name] == 0,
                    "Camera encode failed: " + name + " " + error.decode()[-200:])
        writer.close(confirmed=True)
        (output / "emergency-review.template.json").write_text(json.dumps({
            "assignment_id": AID, "case_id": case,
            "review_kind": "original_native", "review_required": True,
            "road_xodr_sha256": hashlib.sha256(road_xml().encode()).hexdigest(),
            "required_source_names": list(__import__("source_review").SOURCES),
            "qualification_role_requested": config["requested_role"],
            "source_observation_not_yet_confirmed": True}, indent=2) + "\n")
    finally:
        if writer is not None and not writer.closed:
            writer.close(confirmed=False)
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
        restored = restore(client, saved)
    (output / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "native", "diagnostic_fixture": False,
        "native_executed": True}, indent=2) + "\n")
    seal_capture(output, frames=COUNT, restoration=restored, errors=[],
                 encoder_exit_codes=encoder_codes,
                 context={"case_id": case, "source_review_required": True})
    return {"case_id": case, "original_frames": COUNT,
            "capture_sealed": True, "physical_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    config = json.loads((Path(__file__).resolve().parent / "config.json").read_text())
    print(json.dumps(check(config) if args.check else
                     execute(config, args.output_dir, args.host, args.port)))
