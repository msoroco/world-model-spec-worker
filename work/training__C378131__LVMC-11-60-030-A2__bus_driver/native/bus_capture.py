"""Original bus, pedestrian, map and four-camera acquisition. No legal verdict."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess

from .bus_scene import CAMERAS, FRAMES, RATE_HZ, ZONE_KINDS, request, validate
from .bus_construction import constructed_scene

AID = "training__C378131__LVMC-11-60-030-A2__bus_driver"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")


def xyz(value):
    return [value.x, value.y, value.z]


def speed(vector):
    return math.sqrt(vector.x ** 2 + vector.y ** 2 + vector.z ** 2)


def body_vertices(actor):
    return [xyz(point) for point in actor.bounding_box.get_world_vertices(actor.get_transform())]


def apply_controls(carla, scene, bus, passenger, tick):
    policy = scene["controller"]
    if tick < policy["halt_request_frame"]:
        error = scene["ego"]["target_speed_mps"] - speed(bus.get_velocity())
        bus.apply_control(carla.VehicleControl(throttle=max(0, min(.55, .2 * error)),
                                               brake=max(0, min(1, -.4 * error)), steer=0))
    elif tick < policy["resume_request_frame"]:
        bus.apply_control(carla.VehicleControl(throttle=0, brake=1, steer=0,
                                               hand_brake=policy["mechanical_fault_requested"]))
    else:
        bus.apply_control(carla.VehicleControl(throttle=.35, brake=0, steer=0))
    if tick == policy["door_open_request_frame"]:
        bus.open_door(carla.VehicleDoor.FR)
    if tick == policy["door_close_request_frame"]:
        bus.close_door(carla.VehicleDoor.FR)
    walking = policy["passenger_walk_request_frame"] <= tick < policy["door_close_request_frame"]
    if walking:
        position = passenger.get_location()
        target = scene["passenger"]["target_door_xyz"]
        dx, dy = target[0] - position.x, target[1] - position.y
        distance = math.hypot(dx, dy)
        direction = carla.Vector3D(dx / distance, dy / distance, 0) if distance > .05 else carla.Vector3D(0, 0, 0)
        passenger.apply_control(carla.WalkerControl(direction=direction,
                                                   speed=1.0 if distance > .05 else 0))
    else:
        passenger.apply_control(carla.WalkerControl(direction=carla.Vector3D(0, 0, 0), speed=0))


def capture(zone_kind, output, host="127.0.0.1", port=2000, *, vehicle_class="route_bus_non_tour", emergency=False):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import snapshot as world_snapshot, restore as world_restore

    scene = request(zone_kind, vehicle_class=vehicle_class, emergency=emergency)
    validate(scene)
    output = Path(output).resolve()
    if output.exists() and any((output / name).exists() for name in
                               ("video_frames.jsonl", "bus_motion.jsonl", "capture-seal.json")):
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
            core = PipelineCapture(client, actors["ego"], output, AID + "__" + zone_kind,
                                   required_observations=[])
            first_elapsed = None
            with (output / "video_frames.jsonl").open("x") as frame_file, \
                    (output / "bus_motion.jsonl").open("x") as motion_file, \
                    (output / "bus_body.jsonl").open("x") as body_file, \
                    (output / "passenger_body.jsonl").open("x") as passenger_file:
                for i in range(FRAMES):
                    apply_controls(carla, scene, actors["ego"], actors["passenger"], i)
                    native = world.tick()
                    snapshot = world.get_snapshot()
                    if snapshot.frame != native:
                        raise RuntimeError("Native tick/snapshot mismatch")
                    if first_elapsed is None:
                        first_elapsed = snapshot.timestamp.elapsed_seconds
                    elapsed = snapshot.timestamp.elapsed_seconds - first_elapsed
                    if abs(elapsed - i / RATE_HZ) > .005:
                        raise RuntimeError("20 Hz frame join differs")
                    bus, passenger = actors["ego"], actors["passenger"]
                    core.capture(native, elapsed, extra={"bus_loading_source": {
                        "passenger_actor_id": passenger.id,
                        "passenger_position_m": xyz(passenger.get_location()),
                        "passenger_velocity_mps": xyz(passenger.get_velocity())}})
                    frames, hashes = {}, {}
                    for name, incoming in sensors.items():
                        image = incoming.get(timeout=30)
                        if image.frame != native:
                            raise RuntimeError("camera/Native frame mismatch: " + name)
                        frames[name] = image.frame
                        hashes[name] = hashlib.sha256(image.raw_data).hexdigest()
                        encoders[name].stdin.write(image.raw_data)
                    frame = {"video_frame": i, "native_frame": native, "carla_frame": native,
                             "time_s": elapsed, "source_cameras": frames,
                             "camera_rgb_sha256": hashes}
                    frame_file.write(json.dumps(frame, allow_nan=False) + "\n")
                    body_file.write(json.dumps({"native_frame": native, "actor_id": bus.id,
                                                "body_vertices_m": body_vertices(bus)}, allow_nan=False) + "\n")
                    passenger_file.write(json.dumps({"native_frame": native, "actor_id": passenger.id,
                                                     "body_vertices_m": body_vertices(passenger)}, allow_nan=False) + "\n")
                    motion_file.write(json.dumps({**frame, "bus_actor_id": bus.id,
                        "passenger_actor_id": passenger.id, "bus_speed_mps": speed(bus.get_velocity()),
                        "bus_center_m": xyz(bus.get_location()),
                        "passenger_center_m": xyz(passenger.get_location()),
                        "door_open_request_active": 140 <= i < 420,
                        "mechanical_fault_request_active": emergency and 90 <= i < 480,
                        "actual_door_state_observed": False,
                        "actual_passenger_transfer_observed": False,
                        "emergency_requested": emergency}, allow_nan=False) + "\n")
            for process in encoders.values():
                process.stdin.close()
                if process.wait(timeout=120) != 0:
                    raise RuntimeError("source camera encoder failed")
            for name in CAMERAS:
                count = subprocess.check_output(
                    ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                     "-show_entries", "stream=nb_read_frames", "-of", "default=nokey=1:noprint_wrappers=1",
                     str(output / (name + ".mkv"))], text=True, timeout=120).strip()
                if count != str(FRAMES):
                    raise ValueError("source camera frame count differs: " + name)
            core.close(confirmed=True)
            core = None
            sources = {"native_map": "road.xodr", "motion": "bus_motion.jsonl",
                       "bus_body": "bus_body.jsonl", "passenger_body": "passenger_body.jsonl",
                       "camera_manifest": "video_frames.jsonl"}
            write_json(output / "bus_context.json", {
                "source_kind": "original_native_bus_readback", "zone_kind_requested": zone_kind,
                "zone_id": scene["zone_id"], "route_id_requested": scene["route_id"],
                "vehicle_class_requested": vehicle_class,
                "vehicle_class_independently_confirmed": False,
                "emergency_requested": emergency, "emergency_independently_confirmed": False,
                "designation_authority_confirmed": False,
                "actual_loading_confirmed": False, "physical_acceptance_claimed": False,
                "source_files": sources,
                **{key + "_sha256": sha(output / filename) for key, filename in sources.items()}})
        restored = world_restore(client, prior)
        write_json(output / "acquisition-provenance.json", {
            "provenance_kind": "native", "diagnostic_fixture": False,
            "native_executed": True, "physical_acceptance_claimed": False})
        seal_capture(output, frames=FRAMES, restoration=restored, errors=[],
                     encoder_exit_codes={name: process.returncode for name, process in encoders.items()},
                     context={"zone_kind_requested": zone_kind,
                              "actual_loading_confirmed": False, "physical_acceptance_claimed": False})
        return {"source_frames": FRAMES, "original_capture_saved": True,
                "physical_acceptance_claimed": False}
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
    parser.add_argument("--zone-kind", choices=ZONE_KINDS)
    parser.add_argument("--vehicle-class", default="route_bus_non_tour")
    parser.add_argument("--emergency", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps({"zone_kinds": ZONE_KINDS, "camera_names": CAMERAS,
                          "planned_frames": FRAMES, "original_native_observed": False}))
    else:
        if not args.zone_kind or not args.output_dir:
            parser.error("zone kind and fresh output directory required")
        print(json.dumps(capture(args.zone_kind, args.output_dir, args.host, args.port,
                                 vehicle_class=args.vehicle_class, emergency=args.emergency)))
