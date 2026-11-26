"""Original-frame 20 Hz capture for the two exact conditional-yield attempts."""

import argparse
import hashlib
import json
import math
import queue
import subprocess
from pathlib import Path

from native_construction import constructed_scene
from yield_crosswalk_scene import CAMERAS, CASES, request, validate

AID = "training__C111343__NRS-484A-450-3__motor_vehicle_driver"
RATE = 20
COUNT = 600


def case_id(slug):
    if slug not in CASES:
        raise ValueError("Unknown exact yield-crosswalk case")
    return AID + "__" + slug


def check():
    scenes = []
    for slug in CASES:
        scene = request(slug)
        checked = validate(scene)
        if checked["camera_count"] != 4 or checked["planned_frames"] != COUNT:
            raise ValueError("Exact camera or duration plan differs")
        scenes.append({"case_id": case_id(slug),
                       "requested_stop_front_x_m": scene["controller"]["requested_stop_front_x_m"]})
    return {"cases": scenes, "source_cameras": sorted(CAMERAS),
            "duration_s": COUNT / RATE, "rate_hz": RATE,
            "original_native_observed": False, "physical_acceptance_claimed": False,
            "safety_stop_required": "unassessed", "legal_compliance": "unassessed"}


def xyz(value):
    return [value.x, value.y, value.z]


def vertices(actor):
    return [xyz(point) for point in actor.bounding_box.get_world_vertices(actor.get_transform())]


def speed(vector):
    return math.sqrt(vector.x * vector.x + vector.y * vector.y + vector.z * vector.z)


def apply_control(carla, actors, scene, tick):
    """Target a front-bumper stop, then release; saved telemetry decides what occurred."""
    ego = actors["ego"]
    front = max(point[0] for point in vertices(ego))
    current = speed(ego.get_velocity())
    requested = scene["controller"]["requested_stop_front_x_m"]
    remaining = requested - front
    target = 4.0 if tick >= 250 else max(0.0, min(4.0, remaining * 1.2))
    error = target - current
    ego.apply_control(carla.VehicleControl(throttle=max(0.0, min(.65, .24 * error)),
                                           brake=max(0.0, min(1.0, -.45 * error)), steer=0.0))
    other = actors["intersecting"]
    error = scene["intersecting_vehicle"]["requested_speed_mps"] - speed(other.get_velocity())
    other.apply_control(carla.VehicleControl(throttle=max(0.0, min(.65, .24 * error)),
                                             brake=max(0.0, min(1.0, -.45 * error)), steer=0.0))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")


def capture(slug, output, host="127.0.0.1", port=2000):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import snapshot as world_snapshot, restore as world_restore

    scene = request(slug)
    validate(scene)
    output = Path(output).resolve()
    if output.exists() and any((output / name).exists() for name in
                               ("video_frames.jsonl", "yield_motion.jsonl", "capture", "capture-seal.json")):
        raise ValueError("Retain prior Native attempt; choose a fresh materialized attempt")
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
                name = spec["name"]
                incoming = queue.Queue()
                actors["cameras"][name].listen(incoming.put)
                sensors[name] = incoming
                encoders[name] = subprocess.Popen(
                    ["ffmpeg", "-v", "error", "-f", "rawvideo", "-pixel_format", "bgra",
                     "-video_size", f"{spec['size'][0]}x{spec['size'][1]}", "-framerate", str(RATE),
                     "-i", "-", "-frames:v", str(COUNT), "-c:v", "ffv1", str(output / (name + ".mkv"))],
                    stdin=subprocess.PIPE)
            core = PipelineCapture(client, actors["ego"], output, case_id(slug),
                                   required_observations=[])
            first_elapsed = None
            with (output / "video_frames.jsonl").open("x") as frame_file, \
                    (output / "yield_motion.jsonl").open("x") as motion_file, \
                    (output / "ego_body.jsonl").open("x") as ego_file, \
                    (output / "intersecting_body.jsonl").open("x") as other_file:
                for i in range(COUNT):
                    apply_control(carla, actors, scene, i)
                    native = world.tick()
                    snapshot = world.get_snapshot()
                    if snapshot.frame != native:
                        raise RuntimeError("Original Native tick/snapshot mismatch")
                    if first_elapsed is None:
                        first_elapsed = snapshot.timestamp.elapsed_seconds
                    elapsed = snapshot.timestamp.elapsed_seconds - first_elapsed
                    if abs(elapsed - i / RATE) > .005:
                        raise RuntimeError("Original Native 20 Hz time join differs")
                    ego = actors["ego"]
                    other = actors["intersecting"]
                    ego_body = vertices(ego)
                    other_body = vertices(other)
                    core.capture(native, elapsed, extra={"yield_crosswalk_source": {
                        "intersecting_actor_id": other.id,
                        "intersecting_position_m": xyz(other.get_location()),
                        "intersecting_velocity_mps": xyz(other.get_velocity())}})
                    cameras = {}
                    raw_hashes = {}
                    for name, incoming in sensors.items():
                        image = incoming.get(timeout=30)
                        if image.frame != native:
                            raise RuntimeError("Original camera/Native frame mismatch: " + name)
                        cameras[name] = image.frame
                        raw_hashes[name] = hashlib.sha256(image.raw_data).hexdigest()
                        encoders[name].stdin.write(image.raw_data)
                    frame = {"video_frame": i, "native_frame": native, "carla_frame": native,
                             "time_s": elapsed, "source_cameras": cameras,
                             "camera_rgb_sha256": raw_hashes}
                    frame_file.write(json.dumps(frame, allow_nan=False) + "\n")
                    motion_file.write(json.dumps({**frame, "ego_actor_id": ego.id,
                        "intersecting_actor_id": other.id, "ego_x_m": ego.get_location().x,
                        "ego_length_m": max(x[0] for x in ego_body) - min(x[0] for x in ego_body),
                        "ego_speed_mps": speed(ego.get_velocity()),
                        "intersecting_vehicle_y_m": other.get_location().y,
                        "intersecting_speed_mps": speed(other.get_velocity())},
                        allow_nan=False) + "\n")
                    ego_file.write(json.dumps({"native_frame": native, "actor_id": ego.id,
                                               "body_vertices_m": ego_body}, allow_nan=False) + "\n")
                    other_file.write(json.dumps({"native_frame": native, "actor_id": other.id,
                                                 "body_vertices_m": other_body}, allow_nan=False) + "\n")
            for process in encoders.values():
                process.stdin.close()
                if process.wait(timeout=120) != 0:
                    raise RuntimeError("Original source camera encoder failed")
            for name in CAMERAS:
                count = subprocess.check_output(
                    ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                     "-show_entries", "stream=nb_read_frames", "-of", "default=nokey=1:noprint_wrappers=1",
                     str(output / (name + ".mkv"))], text=True, timeout=120).strip()
                if count != str(COUNT):
                    raise ValueError("Original source camera full decode differs: " + name)
            core.close(confirmed=True)
            core = None
            map_hash = sha(output / "road.xodr")
            write_json(output / "yield_sign.json", {"id": "yield-111343",
                "map_readback_sha256": map_hash, "original_map_readback": True})
            write_json(output / "near_crosswalk.json", {"id": "near-crosswalk-111343",
                "near_x_m": scene["crosswalk_near_x_m"], "far_x_m": scene["crosswalk_far_x_m"],
                "map_readback_sha256": map_hash, "original_map_readback": True})
            write_json(output / "intersecting_traffic.json", {"actor_id": actors["intersecting"].id,
                "body_source": "intersecting_body.jsonl", "motion_source": "yield_motion.jsonl",
                "map_readback_sha256": map_hash})
            write_json(output / "safety_context.json", {
                "traffic_source": "intersecting_traffic.json", "motion_source": "yield_motion.jsonl",
                "safety_stop_required": "unassessed", "time_to_conflict_legal_cutoff": None,
                "independent_judgment_required": True})
            sources = {"native_map": "road.xodr", "yield_sign": "yield_sign.json",
                "near_crosswalk": "near_crosswalk.json", "ego_body": "ego_body.jsonl",
                "ego_motion": "yield_motion.jsonl", "intersecting_traffic": "intersecting_traffic.json",
                "safety_context": "safety_context.json", "camera_manifest": "video_frames.jsonl"}
            write_json(output / "yield_context.json", {
                "case_id": case_id(slug), "source_kind": "original_native_yield_crosswalk_readback",
                "source_files": sources, **{key + "_sha256": sha(output / filename)
                                            for key, filename in sources.items()},
                "governing_yield_sign": True, "near_side_crosswalk": True,
                "crosswalk_near_x_m": scene["crosswalk_near_x_m"],
                "crosswalk_far_x_m": scene["crosswalk_far_x_m"],
                "intersection_near_x_m": scene["intersection_near_x_m"],
                "safety_context_present": True, "safety_stop_required": "unassessed",
                "physical_acceptance_claimed": False, "legal_compliance": "unassessed"})
        restored = world_restore(client, prior)
        write_json(output / "acquisition-provenance.json", {
            "provenance_kind": "native", "diagnostic_fixture": False,
            "native_executed": True, "physical_acceptance_claimed": False})
        seal_capture(output, frames=COUNT, restoration=restored, errors=[],
                     encoder_exit_codes={name: process.returncode for name, process in encoders.items()},
                     context={"case_id": case_id(slug), "legal_compliance": "unassessed",
                              "safety_stop_required": "unassessed", "physical_acceptance_claimed": False})
        return {"case_id": case_id(slug), "source_frames": COUNT,
                "original_capture_saved": True, "legal_compliance": "unassessed"}
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
        selected = json.loads(Path(__file__).with_name("config.json").read_text())["selected_case_id"]
        slug = args.case or selected.removeprefix(AID + "__")
        if slug not in CASES or not args.output_dir or case_id(slug) != selected:
            parser.error("Selected exact case and --output-dir are required")
        print(json.dumps(capture(slug, args.output_dir, args.host, args.port), sort_keys=True))
