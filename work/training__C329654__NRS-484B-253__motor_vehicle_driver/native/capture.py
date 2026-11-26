"""Prospective original CARLA acquisition for the two C329654 turn cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import queue
import subprocess
import traceback

from intersection_survey import survey as survey_intersection
from left_turn_controller import apply_vehicle_control, command
from source_capture import sample


FRAMES = 600
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
ASSIGNMENT = "training__C329654__NRS-484B-253__motor_vehicle_driver"
CASES = {ASSIGNMENT + "__selected_d457f261__condition_a": ("yield_then_turn", 15.0),
         ASSIGNMENT + "__selected_d457f261__condition_b": ("turn_before_pass", 9.0)}


def check(config):
    case = config.get("case_id")
    if case not in CASES or config.get("selected_case_id") != case:
        raise ValueError("Exact left-turn case differs")
    if (config.get("law_id"), config.get("cell_id"), config.get("actor"),
            config.get("duration_s"), config.get("rate_hz"),
            config.get("duration_frames")) != (
            "NRS-484B-253", "C329654", "motor_vehicle_driver", 30, 20, FRAMES):
        raise ValueError("Exact law, actor or 600-frame window differs")
    if [item.get("name") for item in config.get("cameras", [])] != list(CAMERAS):
        raise ValueError("Four named Native cameras required")
    if any(item.get("fov_deg") != 90 or not item.get("pose_strategy")
           for item in config["cameras"]):
        raise ValueError("Four-view pose and field-of-view contract differs")
    if (config.get("yield_policy"), config.get("turn_release_s")) != CASES[case]:
        raise ValueError("Controlled original turn policy differs")
    return {"case_id": case, "native_acquisition_implemented": True,
            "original_native_executed": False, "physical_acceptance_claimed": False}


def _new_json(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def _new_line(stream, value):
    stream.write(json.dumps(value, allow_nan=False) + "\n")


def _body(actor):
    return [[vertex.x, vertex.y, vertex.z] for vertex in
            actor.bounding_box.get_world_vertices(actor.get_transform())]


def _camera_pose(carla, name, center):
    x, y = center
    if name == "overview":
        return carla.Transform(carla.Location(x=x - 12, y=y - 12, z=18),
                               carla.Rotation(pitch=-35, yaw=45)), False
    if name == "approach":
        return carla.Transform(carla.Location(x=x - 25, y=y - 3, z=7),
                               carla.Rotation(pitch=-12, yaw=0)), False
    if name == "reference_corner":
        return carla.Transform(carla.Location(x=x + 10, y=y + 10, z=8),
                               carla.Rotation(pitch=-25, yaw=-135)), False
    return carla.Transform(carla.Location(x=.4, y=0, z=1.5),
                           carla.Rotation(pitch=-3)), True


def execute(config, output_dir, host="127.0.0.1", port=2000):
    """Capture requested interaction and retain original readings for saved audit.

    A selected local owner must supply an idle CARLA world with a qualifying
    two-way intersection. This routine never claims the requested motion worked.
    """
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output_dir).resolve()
    if not (output / "config.json").is_file() or not (output / "construction.json").is_file():
        raise ValueError("Use a fresh materialized exact-case attempt")
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    saved = snapshot(client)
    world = client.get_world()
    if saved["settings"].synchronous_mode or any(actor.type_id.startswith(
            ("vehicle.", "walker.", "sensor.", "controller.")) for actor in world.get_actors()):
        raise RuntimeError("Exclusive idle asynchronous Native world required")
    native_map = world.get_map()
    survey, waypoints = survey_intersection(native_map, carla.LaneType.Driving)
    owned, streams, encoders, encoder_logs = [], {}, {}, {}
    pipeline = None
    changed = False
    error = None
    restored = None
    encoder_codes = {}
    count = 0
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        changed = True
        world.set_weather(carla.WeatherParameters.ClearNoon)
        _new_json(output / "map-survey.json", survey)
        _new_json(output / "road_geometry.json", {
            "source_kind": "original_native", "map_sha256": survey["source_sha256"],
            "intersection_polygon_xy_m": survey["intersection_polygon_xy_m"],
            "junction_id": survey["junction_id"], "physical_review_required": True})
        model = world.get_blueprint_library().find("vehicle.lincoln.mkz_2020")
        actors = []
        for role, key in (("subject", "ego_start"), ("initial", "initial_start"),
                          ("subsequent", "subsequent_start")):
            model.set_attribute("role_name", "c329654_" + role)
            actor = world.spawn_actor(model, waypoints[key].transform)
            if actor is None:
                raise RuntimeError("Native actor spawn failed: " + role)
            owned.append(actor)
            actors.append(actor)
        ego, initial, subsequent = actors
        ego.set_light_state(carla.VehicleLightState.LeftBlinker)
        for item in config["cameras"]:
            name = item["name"]
            bp = world.get_blueprint_library().find("sensor.camera.rgb")
            bp.set_attribute("image_size_x", str(item["width"]))
            bp.set_attribute("image_size_y", str(item["height"]))
            bp.set_attribute("fov", str(item["fov_deg"]))
            bp.set_attribute("sensor_tick", "0")
            pose, attached = _camera_pose(carla, name, survey["conflict_xy_m"])
            camera = world.spawn_actor(bp, pose, attach_to=ego if attached else None)
            if camera is None:
                raise RuntimeError("Native camera spawn failed: " + name)
            owned.append(camera)
            streams[name] = queue.Queue()
            camera.listen(streams[name].put)
            encoder_logs[name] = (output / (name + ".encoder.log")).open("x")
            encoders[name] = subprocess.Popen([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                "-f", "rawvideo", "-pix_fmt", "bgra", "-s",
                f'{item["width"]}x{item["height"]}', "-r", "20", "-i", "pipe:0",
                "-an", "-c:v", "ffv1", str(output / (name + ".mkv"))],
                stdin=subprocess.PIPE, stderr=encoder_logs[name])
        pipeline = PipelineCapture(client, ego, output, config["case_id"],
            visibility=False, required_observations=config.get("required_atoms", []))
        with FrameMap(output / "video_frames.jsonl") as frame_map, (
                output / "left-turn-actors.jsonl").open("x") as actor_rows, (
                output / "camera-frames.jsonl").open("x") as camera_rows, (
                output / "interaction_history.jsonl").open("x") as bodies:
            for index in range(FRAMES):
                previous = world.get_snapshot().frame
                observed = sample(previous, index, index / 20, config["case_id"],
                    ego, initial, subsequent, survey, int(carla.VehicleLightState.LeftBlinker),
                    native_map=native_map)
                observed["route_target_xy_m"] = survey["turn_end_xy_m"]
                requested = command(config, observed)
                apply_vehicle_control(ego, requested["ego"])
                apply_vehicle_control(initial, requested["initial_opponent"])
                apply_vehicle_control(subsequent, requested["subsequent_opponent"])
                native_frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native_frame:
                    raise RuntimeError("Native tick/snapshot identity differs")
                row = sample(native_frame, index, index / 20, config["case_id"],
                    ego, initial, subsequent, survey, int(carla.VehicleLightState.LeftBlinker),
                    native_map=native_map)
                row["native_elapsed_s"] = snap.timestamp.elapsed_seconds
                row["requested_controls"] = requested
                _new_line(actor_rows, row)
                _new_line(bodies, {"frame": native_frame, "time_s": index / 20,
                    "subject_body_vertices_m": _body(ego),
                    "source_kind": "original_native"})
                camera_frames, camera_hashes = {}, {}
                for name in CAMERAS:
                    image = streams[name].get(timeout=30)
                    while image.frame < native_frame:
                        image = streams[name].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError("Camera/Native frame join differs: " + name)
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = image.frame
                    camera_hashes[name] = hashlib.sha256(image.raw_data).hexdigest()
                frame_map.append(native_frame, index / 20,
                    camera_native_frames=camera_frames)
                _new_line(camera_rows, {"frame": index, "native_frame": native_frame,
                    "rgb_sha256": camera_hashes})
                pipeline.capture(native_frame, index / 20,
                    extra={"nrs253_original_actor_source": row})
                count += 1
    except BaseException as exc:
        error = {"type": type(exc).__name__, "message": str(exc),
                 "traceback": traceback.format_exc()}
    finally:
        if pipeline is not None:
            try:
                pipeline.close(confirmed=error is None and count == FRAMES)
            except BaseException as exc:
                error = error or {"pipeline_close_error": str(exc)}
        for name, process in encoders.items():
            try:
                process.stdin.close()
                encoder_codes[name] = process.wait(timeout=180)
                if encoder_codes[name] != 0:
                    error = error or {"encoder_error": name}
            except BaseException as exc:
                error = error or {"encoder_error": name, "message": str(exc)}
            encoder_logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith("sensor."):
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {"actor_cleanup_error": str(exc)}
        if changed:
            try:
                restored = restore(client, saved)
            except BaseException as exc:
                error = error or {"world_restore_error": str(exc)}
        _new_json(output / "native-capture-report.json", {
            "case_id": config["case_id"], "frames": count,
            "expected_frames": FRAMES, "restoration": restored,
            "encoder_exit_codes": encoder_codes, "error": error,
            "physical_acceptance_claimed": False})
    if error or count != FRAMES:
        raise RuntimeError("Native left-turn capture failed; inspect native-capture-report.json")
    seal = seal_capture(output, frames=count, restoration=restored,
                        errors=[], encoder_exit_codes=encoder_codes,
                        context={"law_id": "NRS-484B-253",
                                 "case_id": config["case_id"],
                                 "original_map_survey": "map-survey.json"})
    return {"case_id": config["case_id"], "frames": count,
            "capture_seal": seal["source_digest"],
            "physical_acceptance_claimed": False}
