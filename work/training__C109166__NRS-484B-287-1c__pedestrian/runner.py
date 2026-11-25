"""Acquire original pedestrian, control and camera sources for NRS 484B.287(1)(c).

The operator supplies an independently reviewed survey of the chosen Native map.
This runner checks that survey against the live map and actors before mutation.
Neither a successful capture nor this survey is a legal verdict.
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import shutil
import subprocess
import traceback

from scene import CASES, walker_command

FRAMES = 600
RATE = 20
CAMERAS = (
    ("overview", 1920, 1080),
    ("approach", 1280, 720),
    ("reference_corner", 1280, 720),
    ("driver_reference", 1280, 720),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_config(config):
    case = config.get("requested_crossing_location")
    if (config.get("assignment_id") != "training__C109166__NRS-484B-287-1c__pedestrian"
            or case not in CASES
            or config.get("case_id") != config["assignment_id"] + "__" + case
            or config.get("rate_hz") != RATE
            or config.get("duration_s") != 30
            or config.get("frames") != FRAMES):
        raise ValueError("Exact crossing identity and 600-frame capture required")
    if config.get("camera_dimensions") != {name: [w, h] for name, w, h in CAMERAS}:
        raise ValueError("Four source cameras at profile dimensions required")
    if config.get("candidate_id") not in ("primary", "fallback1"):
        raise ValueError("Exact selected candidate required")
    height = config.get("detail_camera_height_m")
    if height != (5.0 if config["candidate_id"] == "primary" else 3.0):
        raise ValueError("Candidate camera-height change differs")
    return {"case_id": config["case_id"], "candidate": config["candidate_id"],
            "frames": FRAMES, "camera_count": 4, "native_executed": False,
            "official_status_verified": False}


def validate_survey(survey, original_map, world):
    """Require a reviewed, map-bound pair; never infer adjacency from x positions."""
    if (survey.get("format") != "c109166-287-1c-native-survey-v1"
            or survey.get("review_status") != "independently_reviewed"
            or not survey.get("independent_reviewer")
            or survey.get("opendrive_sha256") != hashlib.sha256(original_map.to_opendrive().encode()).hexdigest()
            or survey.get("adjacent_intersections_reviewed") is not True
            or survey.get("no_intervening_intersection_reviewed") is not True):
        raise ValueError("Independent original adjacent-intersection map survey required")
    junction_ids = survey.get("junction_ids")
    if not (isinstance(junction_ids, list) and len(junction_ids) == 2
            and len(set(junction_ids)) == 2 and all(type(v) is int for v in junction_ids)):
        raise ValueError("Two distinct surveyed Native junction IDs required")
    live = {waypoint.get_junction().id for waypoint in original_map.generate_waypoints(2.0)
            if waypoint.is_junction}
    if not set(junction_ids) <= live:
        raise ValueError("Surveyed junction absent from original Native topology")
    sites = survey.get("crossing_locations")
    if (not isinstance(sites, dict) or set(sites) != set(CASES)
            or any(sites[name] != x for name, x in CASES.items())):
        raise ValueError("Two exact surveyed crossing sites required")
    controls = survey.get("controls")
    if not isinstance(controls, list) or len(controls) != 2:
        raise ValueError("Two reviewed official control sources required")
    actors = {actor.id: actor for actor in world.get_actors()
              if actor.type_id.startswith("traffic.traffic_light")}
    selected = []
    for record in controls:
        actor_id = record.get("native_actor_id")
        if (type(actor_id) is not int or actor_id not in actors
                or record.get("junction_id") not in junction_ids
                or record.get("official_status_reviewed") is not True
                or not record.get("source_media_sha256")
                or str(actors[actor_id].get_opendrive_id()) != str(record.get("opendrive_id"))):
            raise ValueError("Surveyed official control does not bind Native actor")
        selected.append(actors[actor_id])
    if len({actor.id for actor in selected}) != 2:
        raise ValueError("Two distinct live control actors required")
    crossing = survey.get("marked_crosswalk")
    if (not isinstance(crossing, dict)
            or crossing.get("original_marking_reviewed") is not True
            or not crossing.get("source_media_sha256")
            or not isinstance(crossing.get("polygon_xy_m"), list)
            or len(crossing["polygon_xy_m"]) < 4):
        raise ValueError("Original marked-crosswalk survey required")
    native_marking_points = original_map.get_crosswalks()
    if not any(abs(point.x - CASES["marked_crosswalk"]) <= 3.0
               for point in native_marking_points):
        raise ValueError("Surveyed marked crosswalk absent from Native map readback")
    boundary = survey.get("roadway_boundary")
    if (not isinstance(boundary, dict) or not isinstance(boundary.get("entry_y_m"), (int, float))
            or not math.isfinite(boundary["entry_y_m"])):
        raise ValueError("Original roadway entry boundary required")
    return selected


def copy_survey_media(survey, source_dir, output):
    """Bind every independent map, device, and marking source to original bytes."""
    records = [survey.get("map_source"), survey.get("marked_crosswalk"),
               *survey.get("controls", [])]
    seen = set()
    copied = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Original survey source record missing")
        name = record.get("source_media_path")
        digest = record.get("source_media_sha256")
        if not isinstance(name, str) or not isinstance(digest, str):
            raise ValueError("Original survey media path/hash missing")
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError("Survey media path escapes source directory")
        source = (source_dir / relative).resolve()
        if not source.is_relative_to(source_dir.resolve()) or not source.is_file() or sha(source) != digest:
            raise ValueError("Original survey media hash differs: " + name)
        if name in seen:
            raise ValueError("Independent survey sources must have distinct media")
        seen.add(name)
        destination = output / "native-survey-media" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise ValueError("Survey media already exists in attempt")
        shutil.copy2(source, destination)
        if sha(destination) != digest:
            raise ValueError("Copied original survey media changed")
        copied[name] = digest
    return copied


def _write_new(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")


def _camera_pose(carla, spec, x, detail_height):
    name = spec[0]
    if name == "overview":
        return carla.Transform(carla.Location(x=50, y=-18, z=25), carla.Rotation(pitch=-50, yaw=90))
    if name == "approach":
        return carla.Transform(carla.Location(x=x, y=-10, z=2), carla.Rotation(pitch=0, yaw=90))
    if name == "reference_corner":
        return carla.Transform(carla.Location(x=40, y=12, z=detail_height), carla.Rotation(pitch=-20, yaw=180))
    return carla.Transform(carla.Location(x=50, y=15, z=25), carla.Rotation(pitch=-50, yaw=180))


def execute(config, output, survey_path, host, port):
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from scenario_pipeline.worker_exchange.native_output import FrameMap
    from scenario_pipeline.worker_exchange.world_restore import snapshot, restore

    check_config(config)
    output = Path(output).resolve()
    survey_path = Path(survey_path).resolve()
    if not output.is_dir() or not (output / "config.json").is_file():
        raise ValueError("Fresh materialized attempt with config required")
    if not survey_path.is_file():
        raise ValueError("Original reviewed Native survey source required")
    survey = json.loads(survey_path.read_text())
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    world = client.get_world()
    state = snapshot(client)
    if state["settings"].synchronous_mode:
        raise ValueError("Exclusive idle asynchronous Native world required")
    controls = validate_survey(survey, world.get_map(), world)
    copied_media = copy_survey_media(survey, survey_path.parent, output)
    _write_new(output / "native-survey.json", survey)
    _write_new(output / "native-survey-provenance.json", {
        "source_sha256": sha(survey_path), "copied_sha256": sha(output / "native-survey.json"),
        "copied_media": copied_media})
    _write_new(output / "exception-applicability-source.json", {
        "format": "c109166-287-1c-exception-context-v1",
        "statute": "NRS 484B.290", "review_status": "pending_independent_review",
        "applicability": "undetermined", "source_text_available_in_frozen_assignment": False,
        "legal_verdict": None})
    owned, encoders, encoder_logs, streams = [], {}, {}, {}
    capture = None
    error = None
    restored = None
    changed = False
    frames = 0
    encoder_exit_codes = {}
    old_controls = [(actor, actor.get_state(), actor.is_frozen()) for actor in controls]
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE
        world.apply_settings(settings)
        changed = True
        blueprints = sorted(world.get_blueprint_library().filter("walker.pedestrian.*"), key=lambda bp: bp.id)
        if not blueprints:
            raise ValueError("Native pedestrian blueprint absent")
        x = CASES[config["requested_crossing_location"]]
        walker = world.try_spawn_actor(blueprints[0], carla.Transform(
            carla.Location(x=x, y=-10, z=0.5), carla.Rotation(yaw=90)))
        if walker is None:
            raise ValueError("Native pedestrian spawn failed")
        owned.append(walker)
        for name, width, height in CAMERAS:
            blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
            for key, value in (("image_size_x", width), ("image_size_y", height),
                               ("fov", 90), ("sensor_tick", 0)):
                blueprint.set_attribute(key, str(value))
            camera = world.spawn_actor(blueprint, _camera_pose(
                carla, (name, width, height), x, config["detail_camera_height_m"]))
            if camera is None:
                raise ValueError("Native source camera spawn failed: " + name)
            owned.append(camera)
            streams[name] = queue.Queue()
            camera.listen(streams[name].put)
            encoder_logs[name] = (output / (name + ".encoder.log")).open("x")
            encoders[name] = subprocess.Popen([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}",
                "-r", str(RATE), "-i", "pipe:0", "-an", "-c:v", "ffv1", "-level", "1",
                str(output / (name + ".mkv"))], stdin=subprocess.PIPE,
                stderr=encoder_logs[name])
        capture = PipelineCapture(client, walker, output, config["case_id"],
                                  visibility=False, required_observations=config.get("required_atoms", []))
        start = world.get_snapshot().timestamp.elapsed_seconds
        previous_y = None
        with FrameMap(output / "video_frames.jsonl") as frame_map, \
                (output / "pedestrian-original.jsonl").open("x") as walkers, \
                (output / "controls-original.jsonl").open("x") as devices, \
                (output / "camera-sources.jsonl").open("x") as camera_rows:
            for index in range(FRAMES):
                observed_before = walker.get_transform().location
                operating_before = all(str(actor.get_state()).split(".")[-1]
                                       in ("Red", "Yellow", "Green") for actor in controls)
                command = walker_command(config["requested_crossing_location"], index,
                                         (observed_before.x, observed_before.y, observed_before.z),
                                         operating_before)
                walker.apply_control(carla.WalkerControl(
                    carla.Vector3D(*command["direction_xyz"]), command["speed_mps"], False))
                for actor in controls:
                    actor.freeze(False)
                frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds - start
                pose = walker.get_transform().location
                vertices = walker.bounding_box.get_world_vertices(walker.get_transform())
                footprint = sorted({(round(v.x, 5), round(v.y, 5)) for v in vertices})
                if len(footprint) != 4:
                    raise ValueError("Original pedestrian footprint incomplete")
                entry_y = survey["roadway_boundary"]["entry_y_m"]
                entered = previous_y is not None and previous_y < entry_y <= pose.y
                previous_y = pose.y
                walker_row = {"native_frame": frame, "time_s": time_s,
                              "walker_actor_id": walker.id, "center_xy_m": [pose.x, pose.y],
                              "footprint_xy_m": footprint, "roadway_entry_observed": entered}
                device_row = {"native_frame": frame, "time_s": time_s,
                              "controls": [{"native_actor_id": actor.id,
                                            "opendrive_id": str(actor.get_opendrive_id()),
                                            "native_state": str(actor.get_state()).split(".")[-1],
                                            "frozen": actor.is_frozen(),
                                            "operating_observed": str(actor.get_state()).split(".")[-1]
                                            in ("Red", "Yellow", "Green")}
                                           for actor in controls]}
                capture.capture(frame, time_s, extra={"crossing_observation": {
                    "pedestrian": walker_row, "devices": device_row}})
                pixel_hashes = {}
                for name, width, height in CAMERAS:
                    image = streams[name].get(timeout=30)
                    while image.frame < frame:
                        image = streams[name].get(timeout=30)
                    if image.frame != frame:
                        raise ValueError("Original source camera/frame join failed")
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        height, width, 4)[:, :, :3][:, :, ::-1]
                    raw = rgb.tobytes()
                    pixel_hashes[name] = hashlib.sha256(raw).hexdigest()
                    encoders[name].stdin.write(raw)
                    camera_rows.write(json.dumps({"camera": name, "video_frame": index,
                        "native_frame": frame, "time_s": time_s, "width": width,
                        "height": height, "rgb_sha256": pixel_hashes[name]}) + "\n")
                walkers.write(json.dumps(walker_row) + "\n")
                devices.write(json.dumps(device_row) + "\n")
                frame_map.append(frame, time_s, source_rgb_sha256=pixel_hashes)
                frames += 1
    except BaseException as exc:
        error = {"type": type(exc).__name__, "message": str(exc),
                 "traceback": traceback.format_exc()}
    finally:
        if capture is not None:
            try:
                capture.close(confirmed=error is None and frames == FRAMES)
            except BaseException as exc:
                error = error or {"capture_close_error": str(exc)}
        for name, encoder in encoders.items():
            try:
                encoder.stdin.close()
                encoder_exit_codes[name] = encoder.wait(timeout=180)
                if encoder_exit_codes[name] != 0:
                    raise ValueError("Lossless source encoder failed: " + name)
            except BaseException as exc:
                error = error or {"encoder_error": str(exc)}
            encoder_logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith("sensor.") and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {"actor_cleanup_error": str(exc)}
        for actor, old_state, old_frozen in old_controls:
            try:
                actor.set_state(old_state)
                actor.freeze(old_frozen)
            except BaseException as exc:
                error = error or {"control_restore_error": str(exc)}
        if changed:
            try:
                restored = restore(client, state)
            except BaseException as exc:
                error = error or {"world_restore_error": str(exc)}
        _write_new(output / "native-capture-report.json", {
            "case_id": config["case_id"], "frames": frames, "expected_frames": FRAMES,
            "error": error, "restoration": restored, "survey_sha256": sha(output / "native-survey.json"),
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False})
        if error:
            _write_new(output / "native-run-status.json", {"errors": [error],
                "frames": frames, "restoration": restored, "diagnostic_fixture": False})
        else:
            from scenario_pipeline.worker_exchange.native_output import seal_capture
            _write_new(output / "acquisition-provenance.json", {
                "provenance_kind": "native", "diagnostic_fixture": False,
                "source_kind": "original_live_carla", "legal_verdict_claimed": False})
            seal_capture(output, frames=frames, restoration=restored, errors=[],
                         encoder_exit_codes=encoder_exit_codes,
                         context={"survey_sha256": sha(output / "native-survey.json")})
    if error:
        raise RuntimeError("Native crossing capture failed; inspect native-capture-report.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--survey", type=Path)
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if args.check:
        print(json.dumps(check_config(config), sort_keys=True))
    else:
        survey = args.survey or os.environ.get("SCENARIO_2871C_SURVEY")
        if not all((args.output_dir, survey, args.host, args.port)):
            raise ValueError("Explicit original attempt, survey and Native endpoint required")
        execute(config, args.output_dir, survey, args.host, args.port)


if __name__ == "__main__":
    main()
