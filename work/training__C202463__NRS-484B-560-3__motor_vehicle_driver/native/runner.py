"""Capture an original reviewed railroad crossing stop and queue in Native CARLA."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import shutil
import subprocess

from source_review import ROLES, reviewed_context

FRAMES = 600
RATE_HZ = 20
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
ASSIGNMENT = "training__C202463__NRS-484B-560-3__motor_vehicle_driver"
VARIANTS = {"probe_a": ("right_single", 2), "probe_b": ("left_single", 2),
            "probe_c": ("left_abreast", 2),
            "probe_d": ("left_abreast_four_lanes", 4),
            "probe_e": ("left_abreast_five_lanes", 5)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(config):
    case = config.get("case_id", "")
    suffix = case.removeprefix(ASSIGNMENT + "__")
    if (case != ASSIGNMENT + "__" + suffix
            or config.get("law_id") != "NRS-484B-560-3"
            or config.get("cell_id") != "C202463"
            or config.get("actor") != "motor_vehicle_driver"
            or (config.get("queue_mode"), config.get("marked_lane_count")) != VARIANTS.get(suffix)):
        raise ValueError("Exact railroad case identity differs")
    if config.get("rate_hz") != RATE_HZ or config.get("duration_s") != 30:
        raise ValueError("600 source frames at 20 Hz required")
    cameras = config.get("cameras", [])
    if (tuple(item.get("name") for item in cameras) != CAMERAS
            or [(item.get("width"), item.get("height")) for item in cameras] !=
            [(1920, 1080), (1280, 720), (1280, 720), (1280, 720)]
            or any(not item.get("pose_strategy") or not item.get("fov_deg")
                   for item in cameras)):
        raise ValueError("Four canonical Native cameras required")
    if config.get("candidate_id") not in ("primary", "fallback1"):
        raise ValueError("Selected candidate differs")
    return {"case_id": case, "frames": FRAMES, "camera_names": CAMERAS,
            "native_executed": False, "stop_authority_verified": False,
            "legal_verdict_claimed": False}


def footprint(actor):
    points = actor.bounding_box.get_world_vertices(actor.get_transform())
    if not points:
        raise ValueError("Native vehicle footprint missing")
    return {"min_x": min(point.x for point in points),
            "max_x": max(point.x for point in points),
            "min_y": min(point.y for point in points),
            "max_y": max(point.y for point in points)}


def _review_before_mutation(review_dir, road_sha, world, config):
    review_dir = Path(review_dir).resolve()
    records = {}
    for role in ROLES:
        record_path = review_dir / (role + ".json")
        source_path = review_dir / (role + ".source.txt")
        if not record_path.is_file() or not source_path.is_file():
            raise ValueError("Original reviewed rail source missing: " + role)
        record = json.loads(record_path.read_text())
        if (record.get("role") != role
                or record.get("road_sha256") != road_sha
                or record.get("source_sha256") != sha(source_path)
                or record.get("review_status") != "independently_reviewed"
                or not record.get("reviewer_id")
                or record.get("provenance_kind") != "original_native"):
            raise ValueError("Original reviewed rail source differs: " + role)
        records[role] = record
    if (records["required-stop"].get("stop_required") is not True
            or not records["required-stop"].get("authority_clause")
            or records["lane-markings"].get("total_marked_lanes") != config["marked_lane_count"]
            or records["right-availability"].get("right_space_reviewed") is not True):
        raise ValueError("Required stop, lane count or available right space unsourced")
    actor_id = records["gate-indication"].get("native_actor_id")
    gate = world.get_actor(actor_id) if type(actor_id) is int else None
    if gate is None:
        raise ValueError("Reviewed original gate actor absent")
    return records, gate


def _gate_state(actor):
    if not hasattr(actor, "get_state"):
        raise ValueError("Original gate state API unavailable")
    state = str(actor.get_state()).casefold()
    if any(word in state for word in ("red", "closed", "stop")):
        return "stop"
    if any(word in state for word in ("green", "open", "release")):
        return "release"
    raise ValueError("Original gate state cannot be classified")


def execute(config, output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output_dir).resolve()
    if not output.is_dir() or (output / "actors.jsonl").exists():
        raise ValueError("Fresh materialized Native attempt required")
    review_dir = os.environ.get("C202463_RAIL_REVIEW_DIR")
    if not review_dir:
        raise ValueError("C202463_RAIL_REVIEW_DIR original source prerequisite missing")
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    world = client.get_world()
    saved = snapshot(client)
    if saved["settings"].synchronous_mode:
        raise ValueError("Exclusive asynchronous Native world required")
    road = world.get_map().to_opendrive()
    road_sha = hashlib.sha256(road.encode()).hexdigest()
    records, gate = _review_before_mutation(review_dir, road_sha, world, config)
    crossing_x = records["rail-crossing"].get("crossing_x_m")
    right_edge = records["right-edge"].get("right_highway_edge_y_m")
    if not all(isinstance(v, (int, float)) and math.isfinite(v)
               for v in (crossing_x, right_edge)):
        raise ValueError("Reviewed original crossing and highway edge missing")
    target_x = crossing_x - 10.0
    target_y = right_edge - 1.5 if config["queue_mode"] == "right_single" else right_edge - 4.5
    other_x = target_x if "abreast" in config["queue_mode"] else target_x - 8.0
    other_y = right_edge - 1.5
    owned, encoders, queues = [], {}, {}
    changed = False
    restoration = {"restored": False}
    completed = 0
    errors = []
    encoder_codes = {}
    failure = None
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE_HZ
        world.apply_settings(settings)
        changed = True
        library = world.get_blueprint_library()
        blueprint = sorted(library.filter("vehicle.*"), key=lambda b: b.id)[0]
        ego = world.spawn_actor(blueprint, carla.Transform(
            carla.Location(x=target_x - 50, y=target_y, z=2), carla.Rotation(yaw=0)))
        other = world.spawn_actor(blueprint, carla.Transform(
            carla.Location(x=other_x, y=other_y, z=2), carla.Rotation(yaw=0)))
        owned.extend((ego, other))
        other.apply_control(carla.VehicleControl(brake=1.0, hand_brake=True))
        (output / "road.xodr").write_text(road)
        inventory = {"road_sha256": road_sha, "crossing_x_m": crossing_x,
            "right_highway_edge_y_m": right_edge,
            "total_marked_lanes": config["marked_lane_count"],
            "gate_actor_id": gate.id, "ego_actor_id": ego.id,
            "other_actor_id": other.id, "native_source": True}
        (output / "rail-inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")
        review_out = output / "rail-review"
        review_out.mkdir(exist_ok=False)
        for role in ROLES:
            for suffix in (".json", ".source.txt"):
                shutil.copy2(Path(review_dir) / (role + suffix), review_out / (role + suffix))
        mounts = {"overview": (crossing_x - 10, right_edge - 18, 22, -35),
                  "approach": (crossing_x - 30, right_edge - 8, 9, -15),
                  "reference_corner": (crossing_x, right_edge + 8, 9, -20),
                  "driver_reference": (crossing_x - 35, right_edge + 7, 10, -20)}
        for spec in config["cameras"]:
            name = spec["name"]
            x, y, z, pitch = mounts[name]
            camera_bp = library.find("sensor.camera.rgb")
            camera_bp.set_attribute("image_size_x", str(spec["width"]))
            camera_bp.set_attribute("image_size_y", str(spec["height"]))
            camera_bp.set_attribute("fov", str(spec["fov_deg"]))
            camera_bp.set_attribute("sensor_tick", str(1 / RATE_HZ))
            camera = world.spawn_actor(camera_bp, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)))
            owned.append(camera)
            q = queue.Queue()
            camera.listen(q.put)
            queues[name] = q
            encoders[name] = subprocess.Popen(["ffmpeg", "-nostdin", "-hide_banner",
                "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgra",
                "-s", f"{spec['width']}x{spec['height']}", "-r", str(RATE_HZ),
                "-i", "-", "-frames:v", str(FRAMES), "-c:v", "ffv1", "-level", "1",
                str(output / (name + ".mkv"))], stdin=subprocess.PIPE,
                stderr=subprocess.PIPE)
        with PipelineCapture(client, ego, output, config["case_id"],
                required_observations=config.get("required_atoms", [])) as capture, \
                FrameMap(output / "video_frames.jsonl") as frame_map, \
                (output / "actors.jsonl").open("x") as actor_rows, \
                (output / "gate.jsonl").open("x") as gate_rows, \
                (output / "trace.jsonl").open("x") as trace_rows:
            initial_time = None
            for index in range(FRAMES):
                pose, velocity = ego.get_transform(), ego.get_velocity()
                speed = math.hypot(velocity.x, velocity.y)
                gap = target_x - pose.location.x
                brake = 1.0 if gap <= config["brake_margin_m"] + max(1.0, speed * speed / 6) else 0.0
                ego.apply_control(carla.VehicleControl(throttle=0.35 if not brake else 0,
                    brake=brake, steer=max(-0.4, min(0.4, (target_y - pose.location.y) * 0.12))))
                frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != frame:
                    raise ValueError("Original Native frame mismatch")
                if initial_time is None:
                    initial_time = snap.timestamp.elapsed_seconds
                time_s = snap.timestamp.elapsed_seconds - initial_time
                camera_frames = {}
                for name, q in queues.items():
                    image = q.get(timeout=30)
                    while image.frame < frame:
                        image = q.get(timeout=30)
                    if image.frame != frame:
                        raise ValueError("Original camera frame mismatch")
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = frame
                frame_map.append(frame, time_s, camera_native_frames=camera_frames)
                capture.capture(frame, time_s, extra={"video_frame": index})
                ego_pose, other_pose = ego.get_transform(), other.get_transform()
                ego_v, other_v = ego.get_velocity(), other.get_velocity()
                row = {"frame": frame, "time_s": time_s, "video_frame": index,
                    "actors": {"ego": {"x_m": ego_pose.location.x, "y_m": ego_pose.location.y,
                         "speed_mps": math.hypot(ego_v.x, ego_v.y),
                         "footprint_m": footprint(ego), "native_actor_id": ego.id},
                        "other": {"x_m": other_pose.location.x, "y_m": other_pose.location.y,
                         "speed_mps": math.hypot(other_v.x, other_v.y),
                         "footprint_m": footprint(other), "native_actor_id": other.id}},
                    "camera_native_frames": camera_frames}
                actor_rows.write(json.dumps(row) + "\n")
                gate_rows.write(json.dumps({"frame": frame, "time_s": time_s,
                    "video_frame": index, "kind": "rail_gate",
                    "native_actor_id": gate.id,
                    "indication": _gate_state(gate),
                    "native_transform": str(gate.get_transform())}) + "\n")
                trace_rows.write(json.dumps({"frame": frame, "time_s": time_s,
                    "position": {"x": ego_pose.location.x, "y": ego_pose.location.y,
                                 "z": ego_pose.location.z},
                    "speed_mps": row["actors"]["ego"]["speed_mps"],
                    "heading_deg": ego_pose.rotation.yaw}) + "\n")
                completed += 1
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            encoder_codes[name] = process.wait(timeout=180)
            if encoder_codes[name]:
                raise RuntimeError("Original camera encoding failed: " + name + stderr.decode()[-300:])
        (output / "geometry.json").write_text(json.dumps({
            "rail_crossing_x_m": crossing_x, "right_highway_edge_y_m": right_edge,
            "total_marked_lanes": config["marked_lane_count"],
            "vehicle_width_m": 1.8, "vehicle_length_m": 4.5}, indent=2) + "\n")
        sources = {"kind": "native_rail_stop_queue",
            "sha256": {name: sha(output / name) for name in
                ("geometry.json", "gate.jsonl", "actors.jsonl")}}
        (output / "sources.json").write_text(json.dumps(sources, indent=2) + "\n")
        (output / "acquisition-provenance.json").write_text(json.dumps({
            "provenance_kind": "native_capture", "road_sha256": road_sha,
            "gate_actor_id": gate.id}, indent=2) + "\n")
        reviewed_context(output)
    except BaseException as error:
        failure = error
        errors.append(f"{type(error).__name__}: {error}")
    finally:
        for process in encoders.values():
            if process.poll() is None:
                process.kill()
                process.wait()
        for actor in reversed(owned):
            try:
                if hasattr(actor, "stop"):
                    actor.stop()
                actor.destroy()
            except Exception:
                pass
        if changed:
            try:
                restoration = restore(client, saved)
            except Exception as error:
                errors.append("world restore: " + str(error))
        (output / "native-run-status.json").write_text(json.dumps({
            "case_id": config["case_id"], "frames": completed,
            "errors": errors, "restoration": restoration,
            "encoder_exit_codes": encoder_codes,
            "capture_finished": completed == FRAMES and failure is None,
            "physical_acceptance_claimed": False}, indent=2) + "\n")
    if failure is not None:
        raise failure
    if errors:
        raise RuntimeError("; ".join(errors))
    seal_capture(output, frames=completed, restoration=restoration, errors=errors,
                 encoder_exit_codes=encoder_codes,
                 context={"case_id": config["case_id"],
                          "required_stop_source_reviewed": True,
                          "legal_verdict_claimed": False})
    return {"frames": completed, "original_native_capture": True,
            "physical_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path("config.json").read_text())
    if args.check:
        print(json.dumps(check(config)))
    else:
        if not args.output_dir:
            raise SystemExit("--output-dir required")
        print(json.dumps(execute(config, args.output_dir, args.host, args.port)))
