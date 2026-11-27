"""C111331 source-capturing steady-red straight-travel construction.

The offline check never imports CARLA. Local execution requires an original
map/signal survey; authored targets are kept separate from measured samples.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import traceback


ASSIGNMENT = "training__C111331__NRS-484B-307-8a__motor_vehicle_driver"
CASES = {ASSIGNMENT + "__probe_a": "halt_until_green",
         ASSIGNMENT + "__probe_b": "continue_on_red"}
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check(config):
    require(config.get("case_id") in CASES and
            config.get("selected_case_id") == config.get("case_id") and
            config.get("law_id") == "NRS-484B-307-8a" and
            config.get("cell_id") == "C111331" and
            config.get("actor") == "motor_vehicle_driver", "Wrong exact assignment")
    require(config.get("frozen_cell") == {"layout": "intersection", "maneuver": "travel",
                                          "control": "traffic_light"}, "Frozen cell differs")
    require(config.get("rate_hz") == 20 and config.get("duration_s") == 24 and
            config.get("frames") == 480, "Exact 24-second source window required")
    require(config.get("controller") == CASES[config["case_id"]],
            "Case-specific stop request changed")
    cameras = config.get("cameras", [])
    require(tuple(x.get("name") for x in cameras) == VIEWS and
            [(x.get("width"), x.get("height")) for x in cameras] ==
            [(1920, 1080), (1280, 720), (1280, 720), (1280, 720)] and
            all(x.get("fps") == 20 and x.get("pose_strategy") and
                len(x.get("location_xyz_m", [])) == 3 and
                len(x.get("rotation_pyr_deg", [])) == 3 for x in cameras),
            "Exact four-camera acquisition plan differs")
    require(config.get("original_survey_required") is True and
            config.get("physical_completion") == {} and config.get("legal_verdict") is None,
            "Original source or unverified status changed")
    return {"case_id": config["case_id"], "rate_hz": 20, "frames": 480,
            "cameras": list(VIEWS), "carla_contacted": False,
            "physical_completion": False, "legal_verdict": None}


def read_survey(path):
    survey = json.loads(Path(path).read_text())
    require(survey.get("source_kind") == "original_native_signal_survey" and
            survey.get("map_name") and type(survey.get("vehicle_spawn_index")) is int and
            type(survey.get("governing_signal_actor_id")) is int and
            survey.get("governing_signal_id") and
            survey.get("approach_orientation") == "increasing_y" and
            survey.get("stop_reference_kind") in
            {"nearest_crosswalk", "indicated_sign", "indicated_marking", "intersection_entry"} and
            all(isinstance(survey.get(k), (int, float)) for k in
                ("stop_reference_y_m", "intersection_entry_y_m")) and
            survey.get("approach_lane_side") and
            type(survey.get("approach_lane_extreme")) is bool and
            survey.get("road_geometry_source") and survey.get("stop_reference_source") and
            survey.get("signal_governance_source"),
            "Original Native signal and stop-reference survey required")
    return survey


def request_control(config, front_y_m, speed_mps, stop_y_m, signal_state):
    """Engineering request only; exact observed stop/phase is saved separately."""
    require(math.isfinite(front_y_m) and math.isfinite(speed_mps) and speed_mps >= 0,
            "Original vehicle pose/speed required")
    if config["controller"] == "continue_on_red":
        return {"throttle": 0.22, "brake": 0.0, "phase": "continue_request"}
    distance = stop_y_m - front_y_m
    if signal_state == "Red" and distance < 18:
        brake = min(0.85, max(0.35, 0.35 + speed_mps / 12))
        return {"throttle": 0.0, "brake": brake, "phase": "halt_request"}
    return {"throttle": 0.22, "brake": 0.0, "phase": "green_or_approach_request"}


def _body_front_y(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    require(bool(vertices), "Vehicle body footprint unavailable")
    return max(point.y for point in vertices)


def execute(config, output_dir, survey_path, host, port):
    check(config)
    survey_path = survey_path or os.environ.get("C111331_SIGNAL_SURVEY")
    require(survey_path, "Supply original Native signal survey")
    survey = read_survey(survey_path)
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    output = Path(output_dir)
    require(output.is_dir() and (output / "config.json").is_file(),
            "Use exact materialized construction")
    client = carla.Client(host, port)
    client.set_timeout(15)
    world = client.get_world()
    require(world.get_map().name == survey["map_name"], "Surveyed Native map changed")
    original_world = snapshot(client)
    actors = []
    sensors = []
    images = queue.Queue()
    encoder_codes = {}
    failure = None
    cleanup_errors = []
    restoration = None
    signal = None
    signal_original_state = None
    signal_original_frozen = None
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        spawns = world.get_map().get_spawn_points()
        index = survey["vehicle_spawn_index"]
        require(0 <= index < len(spawns), "Surveyed spawn index unavailable")
        ego = world.try_spawn_actor(world.get_blueprint_library().find(config["vehicle_blueprint"]), spawns[index])
        require(ego is not None, "Surveyed approach spawn occupied")
        actors.append(ego)
        signal = world.get_actor(survey["governing_signal_actor_id"])
        require(signal is not None and signal.type_id == "traffic.traffic_light",
                "Surveyed governing signal unavailable")
        signal_original_state = signal.get_state()
        signal_original_frozen = signal.is_frozen()
        signal.set_state(carla.TrafficLightState.Red)
        signal.freeze(True)
        for camera in config["cameras"]:
            blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
            blueprint.set_attribute("image_size_x", str(camera["width"]))
            blueprint.set_attribute("image_size_y", str(camera["height"]))
            blueprint.set_attribute("fov", str(camera["fov_deg"]))
            x, y, z = camera["location_xyz_m"]
            pitch, yaw, roll = camera["rotation_pyr_deg"]
            sensor = world.spawn_actor(blueprint,
                                       carla.Transform(carla.Location(x=x, y=y, z=z),
                                                       carla.Rotation(pitch=pitch, yaw=yaw, roll=roll)),
                                       attach_to=ego)
            sensors.append(sensor)
            actors.append(sensor)
            (output / camera["name"]).mkdir()
            sensor.listen(lambda image, name=camera["name"]: images.put((name, image)))
        (output / "signal_survey.json").write_bytes(Path(survey_path).read_bytes())
        with PipelineCapture(client, ego, output, config["case_id"],
                             required_observations=config["required_atoms"]) as capture, \
                FrameMap(output / "video_frames.jsonl") as frame_map, \
                (output / "steady-red-native-samples.jsonl").open("x", buffering=1) as trace:
            for frame in range(config["frames"]):
                if frame == config["green_request_frame"]:
                    signal.set_state(carla.TrafficLightState.Green)
                pose = ego.get_transform()
                velocity = ego.get_velocity()
                speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
                front = _body_front_y(ego)
                state_before = str(signal.get_state()).split(".")[-1]
                control = request_control(config, front, speed,
                                          survey["stop_reference_y_m"], state_before)
                ego.apply_control(carla.VehicleControl(throttle=control["throttle"],
                                                       brake=control["brake"], steer=0.0))
                native_frame = world.tick()
                seen = set()
                while len(seen) < len(VIEWS):
                    name, image = images.get(timeout=15)
                    if image.frame != native_frame or name in seen:
                        continue
                    image.save_to_disk(str(output / name / f"{frame:06d}.png"))
                    seen.add(name)
                capture.capture(native_frame, frame / 20,
                                extra={"video_frame": frame,
                                       "governing_signal_actor_id": signal.id})
                frame_map.append(native_frame, frame / 20,
                                 native_elapsed_s=world.get_snapshot().timestamp.elapsed_seconds)
                velocity = ego.get_velocity()
                row = {
                    "frame": frame, "native_frame": native_frame, "time_s": frame / 20,
                    "source_kind": "native_observed",
                    "signal_state": str(signal.get_state()).split(".")[-1].lower(),
                    "governing_signal_id": survey["governing_signal_id"],
                    "ego_front_y_m": _body_front_y(ego),
                    "ego_speed_mps": math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2),
                    "nearest_crosswalk_y_m": survey.get("nearest_crosswalk_y_m"),
                    "indicated_sign_y_m": survey.get("indicated_sign_y_m"),
                    "indicated_marking_y_m": survey.get("indicated_marking_y_m"),
                    "intersection_entry_y_m": survey["intersection_entry_y_m"],
                    "ego_lane_side": survey["approach_lane_side"],
                    "ego_lane_extreme": survey["approach_lane_extreme"],
                    "ego_maneuver": "straight", "approach_one_way": survey.get("approach_one_way"),
                    "downstream_direction": survey.get("downstream_direction"),
                    "pedestrian_priority_present": False, "traffic_priority_present": False,
                    "pedestrian_yielded": False, "traffic_yielded": False,
                    "requested_control": control,
                }
                trace.write(json.dumps(row, sort_keys=True) + "\n")
        for name in VIEWS:
            command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                       "-framerate", "20", "-start_number", "0", "-i",
                       str(output / name / "%06d.png"), "-frames:v", "480", "-an",
                       "-c:v", "ffv1", "-threads", "1", str(output / (name + ".mkv"))]
            completed = subprocess.run(command, timeout=300, capture_output=True, text=True)
            encoder_codes[name] = completed.returncode
            require(completed.returncode == 0, "Camera encode failed: " + name + " " + completed.stderr[-500:])
    except BaseException as error:
        failure = {"type": type(error).__name__, "message": str(error),
                   "traceback": traceback.format_exc()}
        raise
    finally:
        for sensor in sensors:
            try:
                sensor.stop()
            except BaseException as error:
                cleanup_errors.append("sensor_stop: " + str(error))
        for actor in reversed(actors):
            try:
                actor.destroy()
            except BaseException as error:
                cleanup_errors.append("actor_destroy: " + str(error))
        if signal is not None and signal_original_state is not None:
            try:
                signal.set_state(signal_original_state)
                signal.freeze(signal_original_frozen)
            except BaseException as error:
                cleanup_errors.append("signal_restore: " + str(error))
        try:
            restoration = restore(client, original_world)
        except BaseException as error:
            cleanup_errors.append("world_restore: " + str(error))
        if failure or cleanup_errors:
            (output / "native-run-status.json").write_text(json.dumps({
                "errors": ([failure] if failure else []) + cleanup_errors,
                "restoration": restoration, "physical_acceptance_claimed": False}) + "\n")
            if cleanup_errors and not failure:
                raise RuntimeError("Native restoration failed: " + "; ".join(cleanup_errors))
    seal_capture(output, frames=config["frames"], restoration=restoration,
                 errors=[], encoder_exit_codes=encoder_codes,
                 context={"signal_survey_source_kind": survey["source_kind"]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--signal-survey")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path("config.json").read_text())
    if args.check:
        print(json.dumps(check(config)))
    else:
        require(args.output_dir, "Output directory required")
        execute(config, args.output_dir, args.signal_survey, args.host, args.port)
