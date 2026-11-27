"""Original Native crosswalk approach, lead, pedestrian and four-view capture."""
import argparse
import hashlib
import json
from pathlib import Path
import queue
import subprocess

from crosswalk_pass_scene import CASES, CAMERAS, request, validate
from native_construction import constructed_scene

AID = "training__C146108__LVMC-11-30-030__motor_vehicle_driver"
FRAMES = 600
RATE = 20


def case_id(slug):
    if slug not in CASES:
        raise ValueError("Unknown exact crosswalk case")
    return AID + "__" + slug


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")


def xyz(value):
    return [value.x, value.y, value.z]


def body(actor):
    return [xyz(point) for point in actor.bounding_box.get_world_vertices(actor.get_transform())]


def check():
    return {"cases": [validate(request(slug)) for slug in sorted(CASES)],
            "case_ids": [case_id(slug) for slug in sorted(CASES)],
            "camera_names": sorted(CAMERAS), "planned_frames": FRAMES,
            "rate_hz": RATE, "original_native_observed": False,
            "physical_or_legal_acceptance": False}


def control(carla, actors, scene, index):
    ego, lead, pedestrian = actors["ego"], actors["lead"], actors["pedestrian"]
    lead.apply_control(carla.VehicleControl(throttle=0, brake=1, hand_brake=True))
    location = pedestrian.get_location()
    if 120 <= index < 220:
        pedestrian.apply_control(carla.WalkerControl(direction=carla.Vector3D(0, 1, 0), speed=1.4))
    else:
        pedestrian.apply_control(carla.WalkerControl(direction=carla.Vector3D(0, 0, 0), speed=0))
    policy = scene["controller"]["policy"]
    ego_x = ego.get_location().x
    if policy == "hold_behind_lead" and ego_x >= -16:
        ego.apply_control(carla.VehicleControl(throttle=0, brake=1, steer=0))
    else:
        steer = -.3 if policy == "pass_adjacent_lane" and -22 < ego_x < -14 else 0
        ego.apply_control(carla.VehicleControl(throttle=.42, brake=0, steer=steer))


def capture(slug, output, host="127.0.0.1", port=2000):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import snapshot, restore
    scene = request(slug)
    validate(scene)
    output = Path(output).resolve()
    if output.exists() and any((output / name).exists() for name in
                               ("video_frames.jsonl", "crosswalk_trace.jsonl", "capture-seal.json")):
        raise ValueError("Retain prior Native attempt; choose a fresh output")
    output.mkdir(parents=True, exist_ok=True)
    client = carla.Client(host, port)
    client.set_timeout(120)
    prior = snapshot(client)
    encoders = {}
    core = None
    restored = None
    try:
        with constructed_scene(client, carla, scene) as actors:
            world = actors["world"]
            (output / "road.xodr").write_text(actors["map_opendrive"])
            cameras = {}
            for spec in scene["cameras"]:
                incoming = queue.Queue()
                actors["cameras"][spec["name"]].listen(incoming.put)
                cameras[spec["name"]] = incoming
                encoders[spec["name"]] = subprocess.Popen(
                    ["ffmpeg", "-v", "error", "-f", "rawvideo", "-pixel_format", "bgra",
                     "-video_size", f"{spec['size'][0]}x{spec['size'][1]}", "-framerate", "20",
                     "-i", "-", "-frames:v", "600", "-c:v", "ffv1",
                     str(output / (spec["name"] + ".mkv"))], stdin=subprocess.PIPE)
            core = PipelineCapture(client, actors["ego"], output, case_id(slug),
                                   required_observations=[])
            first_elapsed = None
            with (output / "video_frames.jsonl").open("x") as video_stream, \
                    (output / "crosswalk_trace.jsonl").open("x") as trace_stream, \
                    (output / "ego_body.jsonl").open("x") as ego_stream, \
                    (output / "lead_body.jsonl").open("x") as lead_stream, \
                    (output / "pedestrian_body.jsonl").open("x") as pedestrian_stream:
                for index in range(FRAMES):
                    control(carla, actors, scene, index)
                    native = world.tick()
                    snap = world.get_snapshot()
                    if native != snap.frame:
                        raise RuntimeError("Original Native tick/snapshot mismatch")
                    if first_elapsed is None:
                        first_elapsed = snap.timestamp.elapsed_seconds
                    elapsed = snap.timestamp.elapsed_seconds - first_elapsed
                    if abs(elapsed - index / RATE) > .005:
                        raise RuntimeError("Original frame/time join differs")
                    core.capture(native, elapsed, extra={"crosswalk_source": {
                        "lead_actor_id": actors["lead"].id,
                        "pedestrian_actor_id": actors["pedestrian"].id}})
                    source_cameras, hashes = {}, {}
                    for name, incoming in cameras.items():
                        image = incoming.get(timeout=30)
                        if image.frame != native:
                            raise RuntimeError("Original camera/Native frame mismatch: " + name)
                        source_cameras[name] = index
                        hashes[name] = hashlib.sha256(image.raw_data).hexdigest()
                        encoders[name].stdin.write(image.raw_data)
                    frame = {"video_frame": index, "native_frame": native, "carla_frame": native,
                             "time_s": index / RATE, "native_elapsed_s": elapsed,
                             "source_cameras": source_cameras, "camera_rgb_sha256": hashes}
                    video_stream.write(json.dumps(frame, allow_nan=False) + "\n")
                    ego, lead, pedestrian = actors["ego"], actors["lead"], actors["pedestrian"]
                    trace_stream.write(json.dumps({**frame,
                        "ego_x_m": ego.get_location().x, "ego_y_m": ego.get_location().y,
                        "lead_x_m": lead.get_location().x, "lead_y_m": lead.get_location().y,
                        "ego_length_m": 2 * ego.bounding_box.extent.x,
                        "lead_length_m": 2 * lead.bounding_box.extent.x,
                        "lead_speed_mps": lead.get_velocity().length(),
                        "pedestrian_y_m": pedestrian.get_location().y,
                        "ego_speed_mps": ego.get_velocity().length(),
                        "requested_pass_policy": scene["controller"]["policy"],
                        "crosswalk_kind_requested": scene["crosswalk_kind_requested"],
                        "original_lead_stop_purpose_verified": False}, allow_nan=False) + "\n")
                    for actor, stream in ((ego, ego_stream), (lead, lead_stream),
                                          (pedestrian, pedestrian_stream)):
                        stream.write(json.dumps({"native_frame": native, "actor_id": actor.id,
                                                 "body_vertices_m": body(actor)}, allow_nan=False) + "\n")
            for process in encoders.values():
                process.stdin.close()
                if process.wait(timeout=120) != 0:
                    raise RuntimeError("Original source camera encoder failed")
            for name in CAMERAS:
                count = subprocess.check_output(
                    ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                     "-show_entries", "stream=nb_read_frames", "-of", "default=nokey=1:noprint_wrappers=1",
                     str(output / (name + ".mkv"))], text=True, timeout=120).strip()
                if count != "600":
                    raise ValueError("Original camera full decode differs: " + name)
            core.close(confirmed=True)
            core = None
            source_names = ("road.xodr", "crosswalk_trace.jsonl", "ego_body.jsonl",
                            "lead_body.jsonl", "pedestrian_body.jsonl", "video_frames.jsonl")
            put(output / "crosswalk_context.json", {"case_id": case_id(slug),
                "source_kind": "original_native_crosswalk_pass_readback",
                "source_sha256": {name: sha(output / name) for name in source_names},
                "original_intersection_review_required": True,
                "original_lead_stop_purpose_review_required": True,
                "physical_or_legal_acceptance": False})
        restored = restore(client, prior)
        put(output / "acquisition-provenance.json", {"provenance_kind": "native",
            "diagnostic_fixture": False, "native_executed": True,
            "physical_acceptance_claimed": False})
        seal_capture(output, frames=FRAMES, restoration=restored, errors=[],
                     encoder_exit_codes={name: process.returncode for name, process in encoders.items()},
                     context={"case_id": case_id(slug), "physical_acceptance_claimed": False,
                              "original_stop_purpose_review_required": True})
        return {"case_id": case_id(slug), "source_frames": FRAMES,
                "original_capture_saved": True, "physical_or_legal_acceptance": False}
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
            restore(client, prior)
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
            parser.error("Config case differs")
        if slug not in CASES or not args.output_dir:
            parser.error("Selected case and output directory required")
        print(json.dumps(capture(slug, args.output_dir, args.host, args.port), sort_keys=True))
