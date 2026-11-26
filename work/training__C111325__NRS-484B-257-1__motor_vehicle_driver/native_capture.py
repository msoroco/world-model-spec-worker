"""Original-frame Native capture request for NRS 484B.257(1).

The CPU check validates the authored runner without CARLA. A live attempt must
use a fresh output directory and a dedicated local CARLA server. Saved motion
and pixels are observations; this runner makes no legal or physical verdict.
"""

import argparse
import hashlib
import json
import math
import queue
import subprocess
from pathlib import Path

from native_construction import constructed_scene
from stop_yield_scene import CASES, CAMERAS, request, validate

AID = "training__C111325__NRS-484B-257-1__motor_vehicle_driver"
COUNT = 600
RATE = 20


def case_id(slug):
    if slug not in CASES:
        raise ValueError("Unknown exact stop/yield case")
    return AID + "__" + slug


def check():
    config_path = Path(__file__).with_name("config.json")
    config = json.loads(config_path.read_text())
    selected = config.get("selected_case_id")
    if (config.get("assignment_id") != AID or selected not in
            {case_id(slug) for slug in CASES} or config.get("rate_hz") != RATE or
            config.get("frames") != COUNT or config.get("duration_s") != COUNT / RATE or
            {item.get("name") for item in config.get("cameras", [])} != CAMERAS):
        raise ValueError("Bundled exact case or camera/duration plan differs")
    summaries = []
    for slug in sorted(CASES):
        scene = request(slug)
        checked = validate(scene)
        if checked["planned_frames"] != COUNT or checked["camera_count"] != len(CAMERAS):
            raise ValueError("Native capture request differs from canonical profile")
        summaries.append({"case_id": case_id(slug), "reference": checked["stopping_reference"],
                          "exception": checked["control_exception"]})
    return {"selected_case_id": selected, "case_count": len(summaries), "cases": summaries, "carla_imported": False,
            "physical_acceptance_claimed": False, "legal_verdict": None}


def xyz(value):
    return [value.x, value.y, value.z]


def speed(value):
    return math.sqrt(value.x * value.x + value.y * value.y + value.z * value.z)


def body(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    return [xyz(point) for point in vertices]


def body_length_x(vertices):
    return max(point[0] for point in vertices) - min(point[0] for point in vertices)


def body_length_y(vertices):
    return max(point[1] for point in vertices) - min(point[1] for point in vertices)


def apply_requested_control(carla, actors, scene, tick_index):
    """Request two independent motions; measured telemetry is saved after tick."""
    ego = actors["ego"]
    through = actors["through"]
    control = scene["controller"]
    front = max(point[0] for point in body(ego))
    current = speed(ego.get_velocity())
    if control["policy"] == "roll_through":
        target = 4.0
    elif tick_index < control["release_frame"]:
        remaining = control["stop_front_x_m"] - front
        target = max(0.0, min(4.0, remaining * 1.2))
    else:
        target = 4.0
    error = target - current
    ego.apply_control(carla.VehicleControl(throttle=max(0.0, min(.65, .24 * error)),
                                           brake=max(0.0, min(1.0, -.45 * error)), steer=0.0))
    other = speed(through.get_velocity())
    through_error = scene["through_vehicle"]["requested_speed_mps"] - other
    through.apply_control(carla.VehicleControl(throttle=max(0.0, min(.65, .24 * through_error)),
                                               brake=max(0.0, min(1.0, -.45 * through_error)), steer=0.0))


def source_file(output, name, value):
    path = output / name
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(slug, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import snapshot as world_snapshot, restore as world_restore

    scene = request(slug)
    validate(scene)
    if scene["police_controlling"] or scene["signal_controlling"]:
        raise ValueError("Control exception needs original per-frame direction/state implementation")
    if scene["stopping_reference"] == "nearest_viewpoint":
        raise ValueError("Nearest-viewpoint branch needs original through-highway sight rays")
    output = Path(output).resolve()
    if output.exists() and any((output / name).exists() for name in
                               ("video_frames.jsonl", "stop_yield_motion.jsonl", "trace.jsonl", "capture")):
        raise ValueError("Retain prior attempt; choose a fresh Native output directory")
    output.mkdir(parents=True, exist_ok=True)
    config_source = Path(__file__).with_name("config.json")
    config_target = output / "config.json"
    if not config_target.exists():
        config_target.write_bytes(config_source.read_bytes())
    config = json.loads(config_target.read_text())
    if config.get("selected_case_id") != case_id(slug):
        raise ValueError("Native selected-case config differs from requested case")
    client = carla.Client(host, port)
    client.set_timeout(120)
    prior_world = None
    encoders = {}
    core = None
    restoration = None
    try:
        prior_world = world_snapshot(client)
        with constructed_scene(client, carla, scene) as actors:
            world = actors["world"]
            queues = {}
            for spec in scene["cameras"]:
                name = spec["name"]
                q = queue.Queue()
                actors["cameras"][name].listen(q.put)
                queues[name] = q
                encoders[name] = subprocess.Popen(
                    ["ffmpeg", "-v", "error", "-f", "rawvideo", "-pixel_format", "bgra",
                     "-video_size", f"{spec['width']}x{spec['height']}", "-framerate", str(RATE),
                     "-i", "-", "-frames:v", str(COUNT), "-c:v", "ffv1", str(output / (name + ".mkv"))],
                    stdin=subprocess.PIPE)
            core = PipelineCapture(client, actors["ego"], output, case_id(slug), required_observations=[])
            first_elapsed = None
            motion_path = output / "stop_yield_motion.jsonl"
            ego_path = output / "ego_body.jsonl"
            through_path = output / "through_body.jsonl"
            interaction_path = output / "interaction_history.jsonl"
            with (output / "video_frames.jsonl").open("x") as frames, motion_path.open("x") as motion, \
                    ego_path.open("x") as ego_bodies, through_path.open("x") as through_bodies, \
                    interaction_path.open("x") as interactions:
                for i in range(COUNT):
                    apply_requested_control(carla, actors, scene, i)
                    native = world.tick()
                    snapshot = world.get_snapshot()
                    if snapshot.frame != native:
                        raise RuntimeError("Native tick/snapshot identity differs")
                    if first_elapsed is None:
                        first_elapsed = snapshot.timestamp.elapsed_seconds
                    time_s = snapshot.timestamp.elapsed_seconds - first_elapsed
                    if abs(time_s - i / RATE) > .005:
                        raise RuntimeError("Original 20 Hz elapsed-time join differs")
                    ego = actors["ego"]
                    through = actors["through"]
                    ego_body = body(ego)
                    other_body = body(through)
                    ego_loc = ego.get_location()
                    other_loc = through.get_location()
                    core.capture(native, time_s, extra={"stop_yield_source": {
                        "through_actor_id": through.id, "through_position_m": xyz(other_loc),
                        "through_velocity_mps": xyz(through.get_velocity())}})
                    camera_frames = {}
                    camera_rgb_sha256 = {}
                    for name, q in queues.items():
                        image = q.get(timeout=30)
                        if image.frame != native:
                            raise RuntimeError("Source camera frame differs from Native tick: " + name)
                        camera_frames[name] = image.frame
                        camera_rgb_sha256[name] = hashlib.sha256(image.raw_data).hexdigest()
                        encoders[name].stdin.write(image.raw_data)
                    frame_row = {"video_frame": i, "carla_frame": native, "native_frame": native,
                                 "time_s": time_s, "source_cameras": camera_frames,
                                 "camera_rgb_sha256": camera_rgb_sha256}
                    frames.write(json.dumps(frame_row, allow_nan=False) + "\n")
                    motion.write(json.dumps({**frame_row, "ego_actor_id": ego.id,
                        "through_actor_id": through.id, "ego_x_m": ego_loc.x,
                        "ego_length_m": body_length_x(ego_body), "ego_speed_mps": speed(ego.get_velocity()),
                        "through_y_m": other_loc.y, "through_length_m": body_length_y(other_body),
                        "through_speed_mps": speed(through.get_velocity())}, allow_nan=False) + "\n")
                    ego_bodies.write(json.dumps({"native_frame": native, "actor_id": ego.id,
                                                 "body_vertices_m": ego_body}, allow_nan=False) + "\n")
                    through_bodies.write(json.dumps({"native_frame": native, "actor_id": through.id,
                                                     "body_vertices_m": other_body}, allow_nan=False) + "\n")
                    interactions.write(json.dumps({"frame": native, "time_s": time_s,
                        "ego": {"actor_id": ego.id, "body_vertices_m": ego_body},
                        "through": {"actor_id": through.id, "body_vertices_m": other_body}},
                        allow_nan=False) + "\n")
            for process in encoders.values():
                process.stdin.close()
                if process.wait(timeout=120) != 0:
                    raise RuntimeError("Source camera encoder failed")
            for name in queues:
                probe = subprocess.run(
                    ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                     "-show_entries", "stream=nb_read_frames", "-of", "default=nokey=1:noprint_wrappers=1",
                     str(output / (name + ".mkv"))], check=True, text=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
                if probe.stdout.strip() != str(COUNT):
                    raise RuntimeError("Source camera decoded frame count differs: " + name)
            core.close(confirmed=True)
            core = None
            source_paths = {
                "map": output / "road.xodr",
                "sign": source_file(output, "governing_sign.json", {
                    "id": scene["governing_sign"], "map_readback_sha256": sha(output / "road.xodr"),
                    "actor_source": "original CARLA map OpenDRIVE readback"}),
                "reference": source_file(output, "stopping_reference.json", {
                    "kind": scene["stopping_reference"], "stop_line_x_m": scene["stop_line_x_m"],
                    "crosswalk_marking": scene["crosswalk_marking"],
                    "map_readback_sha256": sha(output / "road.xodr")}),
                "controls": source_file(output, "governing_controls.json", {
                    "police_controlling": False, "signal_controlling": False,
                    "governing_sign_id": scene["governing_sign"],
                    "map_readback_sha256": sha(output / "road.xodr")}),
                "through_road": source_file(output, "through_road.json", {
                    "road_id": 111326, "through_actor_id": actors["through"].id,
                    "map_readback_sha256": sha(output / "road.xodr")}),
                "ego_body": ego_path,
                "through_body": through_path,
            }
            source_file(output, "control_context.json", {
                "case_id": case_id(slug), "source_kind": "original_native_readback",
                "intersection_xy_m": [[scene["intersection_near_x_m"], -3.5],
                                      [scene["intersection_far_x_m"], -3.5],
                                      [scene["intersection_far_x_m"], 3.5],
                                      [scene["intersection_near_x_m"], 3.5]],
                "governing_sign_id": scene["governing_sign"],
                "map_readback_sha256": sha(output / "road.xodr")})
            reference = scene["stopping_reference"]
            source_file(output, "stop_yield_context.json", {
                "case_id": case_id(slug), "source_kind": "original_native_readback",
                "source_files": {name: path.name for name, path in source_paths.items()},
                **{name + "_sha256": sha(path) for name, path in source_paths.items()},
                "sign_kind": "yield" if slug.startswith("yield_sign_") else "stop",
                "reference_kind": reference, "marked_line_present": reference == "stop_line",
                "crosswalk_present": reference == "crosswalk", "sight_ray_source": None,
                "police_controlling": False, "signal_controlling": False,
                "controlling_direction_source": None,
                "reference_x_m": scene["stop_line_x_m"] if reference == "stop_line" else
                                   scene["crosswalk_marking"]["near_edge_x_m"] if reference == "crosswalk" else
                                   scene["nearest_viewpoint_candidate"]["front_x_m"],
                "intersection_near_x_m": scene["intersection_near_x_m"],
                "intersection_far_x_m": scene["intersection_far_x_m"],
                "through_conflict_halfwidth_m": 3.5,
                "physical_acceptance_claimed": False, "legal_verdict": None})
        restoration = world_restore(client, prior_world)
        source_file(output, "acquisition-provenance.json", {"provenance_kind": "native",
                    "diagnostic_fixture": False, "physical_acceptance_claimed": False})
        seal_capture(output, frames=COUNT, restoration=restoration,
                     errors=[], encoder_exit_codes={name: process.returncode for name, process in encoders.items()},
                     context={"case_id": case_id(slug), "original_native_readback": True,
                              "legal_verdict": None, "physical_acceptance_claimed": False})
        return {"case_id": case_id(slug), "source_frames": COUNT,
                "original_capture_saved": True, "physical_acceptance_claimed": False,
                "legal_verdict": None}
    except BaseException as error:
        if core is not None:
            try:
                core.close(confirmed=False)
            except BaseException as close_error:
                error = RuntimeError("Native attempt and recorder closure both failed: " +
                                     str(error) + "; " + str(close_error))
            core = None
        for process in encoders.values():
            if process.poll() is None:
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
                process.kill()
                process.wait()
        if restoration is None and prior_world is not None:
            try:
                restoration = world_restore(client, prior_world)
            except BaseException as restore_error:
                error = RuntimeError("Native attempt and world restoration both failed: " +
                                     str(error) + "; " + str(restore_error))
        if output.is_dir() and not (output / "capture-seal.json").exists():
            source_file(output, "native-run-status.json", {"errors": [{"type": type(error).__name__,
                        "message": str(error)}], "capture_failed": True,
                        "physical_acceptance_claimed": False})
        raise error
    finally:
        if core is not None:
            core.close(confirmed=False)
        for process in encoders.values():
            if process.poll() is None:
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
                process.kill()
                process.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check", action="store_true")
    action.add_argument("--capture", action="store_true")
    parser.add_argument("--case")
    parser.add_argument("--output")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check(), sort_keys=True))
    else:
        destination = args.output_dir or args.output
        selected = json.loads(Path(__file__).with_name("config.json").read_text()).get("selected_case_id", "")
        slug = args.case or selected.removeprefix(AID + "__")
        if not slug or not destination:
            parser.error("Native capture requires --output-dir and selected case")
        print(json.dumps(capture(slug, destination, args.host, args.port), sort_keys=True))
