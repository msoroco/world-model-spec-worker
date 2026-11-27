"""Original-frame acquisition for exact passenger-loading and no-transfer cases."""

import argparse
from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess

from .loading_scene import CAMERAS, CASES, FRAMES, RATE_HZ, request, validate
from .native_construction import constructed_scene

AID = "training__C149498__NRS-484B-503__motor_vehicle_driver"


def case_id(slug):
    if slug not in CASES:
        raise ValueError("unknown exact loading case")
    suffix = "selected_bae4893e__" + slug
    return AID + "__" + suffix


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")


def xyz(value):
    return [value.x, value.y, value.z]


def body_vertices(actor):
    return [xyz(point) for point in actor.bounding_box.get_world_vertices(actor.get_transform())]


def speed(vector):
    return math.sqrt(vector.x ** 2 + vector.y ** 2 + vector.z ** 2)


def check():
    return {"cases": [{"case_id": case_id(slug), "transfer_requested": CASES[slug]}
                      for slug in CASES],
            "camera_names": list(CAMERAS), "planned_frames": FRAMES,
            "rate_hz": RATE_HZ, "original_native_observed": False,
            "physical_transfer_confirmed": False,
            "zone_authority_confirmed": False}


def apply_controls(carla, scene, ego, passenger, tick):
    policy = scene["controller"]
    if tick < policy["halt_request_frame"]:
        current = speed(ego.get_velocity())
        error = scene["ego"]["target_speed_mps"] - current
        ego.apply_control(carla.VehicleControl(throttle=max(0, min(.55, .2 * error)),
                                               brake=max(0, min(1, -.4 * error)), steer=0))
    elif tick < policy["resume_request_frame"]:
        ego.apply_control(carla.VehicleControl(throttle=0, brake=1, steer=0,
                                               hand_brake=policy["action_request"] == "extended_park"))
    else:
        ego.apply_control(carla.VehicleControl(throttle=.35, brake=0, steer=0))
    if policy["door_open_request_frame"] is not None and tick == policy["door_open_request_frame"]:
        ego.open_door(carla.VehicleDoor.FR)
    if policy["door_close_request_frame"] is not None and tick == policy["door_close_request_frame"]:
        ego.close_door(carla.VehicleDoor.FR)
    if scene["passenger"]["cross_doorway_requested"] and (
            policy["door_close_request_frame"] is not None and
            policy["passenger_walk_request_frame"] <= tick < policy["door_close_request_frame"]):
        target = scene["passenger"]["target_door_xyz"]
        position = passenger.get_location()
        dx, dy = target[0] - position.x, target[1] - position.y
        distance = math.hypot(dx, dy)
        direction = carla.Vector3D(dx / distance, dy / distance, 0) if distance > .05 else carla.Vector3D(0, 0, 0)
        passenger.apply_control(carla.WalkerControl(direction=direction, speed=1.0 if distance > .05 else 0))
    else:
        passenger.apply_control(carla.WalkerControl(direction=carla.Vector3D(0, 0, 0), speed=0))


def capture(slug, output, host="127.0.0.1", port=2000):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import snapshot as world_snapshot, restore as world_restore

    scene = request(slug)
    validate(scene)
    output = Path(output).resolve()
    if output.exists() and any((output / name).exists() for name in
                               ("video_frames.jsonl", "loading_motion.jsonl", "capture-seal.json")):
        raise ValueError("retain prior Native attempt; choose a fresh output")
    output.mkdir(parents=True, exist_ok=True)
    client = carla.Client(host, port)
    client.set_timeout(120)
    prior = world_snapshot(client)
    encoders = {}
    core = None
    restored = None
    try:
        with constructed_scene(client, carla, scene) as actors:
            world = actors["world"]
            (output / "road.xodr").write_text(actors["map_opendrive"])
            sensors = {}
            for spec in scene["cameras"]:
                incoming = queue.Queue()
                actors["cameras"][spec["name"]].listen(incoming.put)
                sensors[spec["name"]] = incoming
                encoders[spec["name"]] = subprocess.Popen(
                    ["ffmpeg", "-v", "error", "-f", "rawvideo", "-pixel_format", "bgra",
                     "-video_size", f"{spec['size'][0]}x{spec['size'][1]}", "-framerate", str(RATE_HZ),
                     "-i", "-", "-frames:v", str(FRAMES), "-c:v", "ffv1",
                     str(output / (spec["name"] + ".mkv"))], stdin=subprocess.PIPE)
            core = PipelineCapture(client, actors["ego"], output, case_id(slug),
                                   required_observations=[])
            first_elapsed = None
            civil_start = datetime.fromisoformat(scene["zone"]["civil_timestamp_start"])
            with (output / "video_frames.jsonl").open("x") as frame_file, \
                    (output / "loading_motion.jsonl").open("x") as motion_file, \
                    (output / "ego_body.jsonl").open("x") as body_file, \
                    (output / "passenger_body.jsonl").open("x") as passenger_file:
                for i in range(FRAMES):
                    apply_controls(carla, scene, actors["ego"], actors["passenger"], i)
                    native = world.tick()
                    snapshot = world.get_snapshot()
                    if snapshot.frame != native:
                        raise RuntimeError("original Native tick/snapshot mismatch")
                    if first_elapsed is None:
                        first_elapsed = snapshot.timestamp.elapsed_seconds
                    elapsed = snapshot.timestamp.elapsed_seconds - first_elapsed
                    if abs(elapsed - i / RATE_HZ) > .005:
                        raise RuntimeError("original 20 Hz frame join differs")
                    ego = actors["ego"]
                    passenger = actors["passenger"]
                    core.capture(native, elapsed, extra={"loading_source": {
                        "passenger_actor_id": passenger.id,
                        "passenger_position_m": xyz(passenger.get_location()),
                        "passenger_velocity_mps": xyz(passenger.get_velocity())}})
                    frames = {}
                    raw_hashes = {}
                    for name, incoming in sensors.items():
                        image = incoming.get(timeout=30)
                        if image.frame != native:
                            raise RuntimeError("original camera/Native frame mismatch: " + name)
                        frames[name] = image.frame
                        raw_hashes[name] = hashlib.sha256(image.raw_data).hexdigest()
                        encoders[name].stdin.write(image.raw_data)
                    frame = {"video_frame": i, "native_frame": native,
                             "carla_frame": native, "time_s": elapsed,
                             "source_cameras": frames, "camera_rgb_sha256": raw_hashes}
                    frame_file.write(json.dumps(frame, allow_nan=False) + "\n")
                    body_file.write(json.dumps({"native_frame": native, "actor_id": ego.id,
                                                "body_vertices_m": body_vertices(ego)}, allow_nan=False) + "\n")
                    passenger_file.write(json.dumps({"native_frame": native, "actor_id": passenger.id,
                                                     "body_vertices_m": body_vertices(passenger)}, allow_nan=False) + "\n")
                    motion_file.write(json.dumps({**frame, "ego_actor_id": ego.id,
                        "passenger_actor_id": passenger.id,
                        "vehicle_speed_mps": speed(ego.get_velocity()),
                        "vehicle_center_m": xyz(ego.get_location()),
                        "passenger_center_m": xyz(passenger.get_location()),
                        "door_open_request_active": scene["controller"]["door_open_request_frame"] is not None and scene["controller"]["door_open_request_frame"] <= i < scene["controller"]["door_close_request_frame"],
                        "civil_timestamp": (civil_start + timedelta(seconds=i / RATE_HZ)).isoformat(),
                        "occupant_count_observed": False,
                        "actual_door_state_observed": False}, allow_nan=False) + "\n")
            for process in encoders.values():
                process.stdin.close()
                if process.wait(timeout=120) != 0:
                    raise RuntimeError("original source camera encoder failed")
            for name in CAMERAS:
                count = subprocess.check_output(
                    ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                     "-show_entries", "stream=nb_read_frames", "-of", "default=nokey=1:noprint_wrappers=1",
                     str(output / (name + ".mkv"))], text=True, timeout=120).strip()
                if count != str(FRAMES):
                    raise ValueError("original source camera full decode differs: " + name)
            core.close(confirmed=True)
            core = None
            map_hash = sha(output / "road.xodr")
            write_json(output / "loading_zone.json", {
                "object_id": scene["zone"]["object_id"], "sign_id": scene["zone"]["sign_id"],
                "sign_text_hours": [scene["zone"]["hours_start"], scene["zone"]["hours_end"]],
                "time_zone": scene["zone"]["time_zone"], "map_readback_sha256": map_hash,
                "regulatory_authority_confirmed": False})
            sources = {"native_map": "road.xodr", "zone": "loading_zone.json",
                "motion": "loading_motion.jsonl", "ego_body": "ego_body.jsonl",
                "passenger_body": "passenger_body.jsonl", "camera_manifest": "video_frames.jsonl"}
            write_json(output / "loading_context.json", {
                "case_id": case_id(slug), "source_kind": "original_native_passenger_curb_readback",
                "source_files": sources,
                **{key + "_sha256": sha(output / filename) for key, filename in sources.items()},
                "requested_passenger_transfer": CASES[slug],
                "actual_passenger_transfer_confirmed": False,
                "occupant_count_observed": False,
                "regulatory_authority_confirmed": False,
                "expeditiousness_conclusion": None,
                "physical_acceptance_claimed": False})
        restored = world_restore(client, prior)
        write_json(output / "acquisition-provenance.json", {
            "provenance_kind": "native", "diagnostic_fixture": False,
            "native_executed": True, "physical_acceptance_claimed": False})
        seal_capture(output, frames=FRAMES, restoration=restored, errors=[],
                     encoder_exit_codes={name: process.returncode for name, process in encoders.items()},
                     context={"case_id": case_id(slug), "physical_acceptance_claimed": False,
                              "actual_passenger_transfer_confirmed": False})
        return {"case_id": case_id(slug), "source_frames": FRAMES,
                "original_capture_saved": True, "physical_acceptance_claimed": False}
    except BaseException:
        if core is not None:
            core.close(confirmed=False)
        for process in encoders.values():
            if process.poll() is None:
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
                process.kill()
                process.wait()
        if restored is None:
            world_restore(client, prior)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--case")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check(), sort_keys=True))
    else:
        selected = json.loads(Path("config.json").read_text()).get("selected_case_id", "")
        slug = args.case or selected.rsplit("__", 1)[-1]
        if selected and selected != case_id(slug):
            parser.error("config selected case and requested Native case differ")
        if slug not in CASES or not args.output_dir:
            parser.error("selected case and --output-dir are required")
        print(json.dumps(capture(slug, args.output_dir, args.host, args.port), sort_keys=True))
