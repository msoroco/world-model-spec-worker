"""Native original-tick capture for the three marked-lane exact cases.

CARLA is imported only for capture. All legal and geometric assessment happens
later from sealed original sources in lane_finalizer.py.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lane_camera_capture import CAMERAS, LaneCameraCapture, LosslessSourceSink
from lane_construction import CASE_SUFFIXES, control_step, route_targets, select_marked_one_way_pair
from lane_sources import LaneSourceRecorder


def check_config(config):
    case = config.get("selected_case_id", "")
    suffix = next((name for name in CASE_SUFFIXES if case.endswith("__" + name)), None)
    if suffix is None or config.get("case", {}).get("case_id") != case:
        raise ValueError("Unknown exact marked-lane case")
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "LVMC-11-18-030-B", "C147331", "motor_vehicle_driver"):
        raise ValueError("Runner law/cell/actor identity differs")
    if config.get("construction_probe_only") is True:
        raise ValueError("Probe config is not a Native delivery construction")
    if (config.get("rate_hz"), config.get("frames"), config.get("duration_s")) != (20, 160, 8):
        raise ValueError("Native lane timing must be 160 original frames at 20 Hz")
    if not isinstance(config.get("case", {}).get("recording_description"), dict):
        raise ValueError("Selected recording description is required")
    camera_plan = config.get("cameras", [])
    if not isinstance(camera_plan, list) or {row.get("name") for row in camera_plan} != set(CAMERAS):
        raise ValueError("Four named original cameras are required")
    for row in camera_plan:
        size = CAMERAS[row["name"]][2]
        if (row.get("width"), row.get("height"), row.get("fov_deg")) != (*size, CAMERAS[row["name"]][3]):
            raise ValueError("Original camera dimensions or field of view differ")
    engineering = config.get("engineering", {})
    if not isinstance(engineering, dict) or set(engineering) - {
            "route_spacing_m", "route_steps", "route_candidate_index",
            "target_speed_mps", "speed_gain", "crossing_fraction"}:
        raise ValueError("Unknown lane engineering knob")
    if (engineering.get("route_spacing_m", 2.0), engineering.get("route_steps", 15)) not in (
            (2.0, 15), (1.0, 30)):
        raise ValueError("Unsupported marked-route sampling")
    if engineering.get("route_candidate_index", 0) not in (0, 1):
        raise ValueError("Unsupported marked-route candidate index")
    if (engineering.get("target_speed_mps", 6.0), engineering.get("speed_gain", .25)) not in (
            (6.0, .25), (4.5, .2)):
        raise ValueError("Unsupported lane controller tuning")
    expected_fraction = {"passing_excursion-0000": .4,
                         "passing_excursion-0001": .8,
                         "passing_excursion-0002": .6}.get(suffix, .6)
    if engineering.get("crossing_fraction", .6) != expected_fraction:
        raise ValueError("Crossing sweep value differs from exact case")
    return suffix


def _spawn(world, blueprint_id, transform):
    actor = world.try_spawn_actor(world.get_blueprint_library().find(blueprint_id), transform)
    if actor is None:
        raise ValueError("Native marked-lane actor spawn failed: " + blueprint_id)
    return actor


def _drive(actor, target, carla, engineering):
    transform = actor.get_transform()
    position = transform.location
    direction = transform.get_forward_vector()
    velocity = actor.get_velocity()
    command = control_step([position.x, position.y], [direction.x, direction.y],
                           [velocity.x, velocity.y], target,
                           target_speed_mps=engineering.get("target_speed_mps", 6.0),
                           speed_gain=engineering.get("speed_gain", .25))
    actor.apply_control(carla.VehicleControl(**command))


def run(output_dir, host, port):
    import carla  # Native-only dependency.
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture

    output = Path(output_dir)
    config = json.loads((output / "config.json").read_text())
    suffix = check_config(config)
    engineering = config.get("engineering", {})
    client = carla.Client(host, port)
    client.set_timeout(30.)
    world = client.get_world()
    original = world.get_settings()
    owned = []
    sinks = {}
    cameras = pipeline = recorder = frame_map = None
    frames = []
    errors = []
    restored = False
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / config["rate_hz"]
        world.apply_settings(settings)
        selection = select_marked_one_way_pair(
            world.get_map(), spacing_m=engineering.get("route_spacing_m", 2.0),
            steps=engineering.get("route_steps", 15),
            candidate_index=engineering.get("route_candidate_index", 0))
        targets = route_targets(selection, suffix,
                                crossing_fraction=engineering.get("crossing_fraction", .6))
        ego = _spawn(world, "vehicle.tesla.model3", selection["primary"][0].transform)
        owned.append(ego)
        other = None
        if targets["overtaken_spawn"] is not None:
            other = _spawn(world, "vehicle.audi.tt", targets["overtaken_spawn"])
            owned.append(other)
        for name in CAMERAS:
            sinks[name] = LosslessSourceSink(output, name)
        cameras = LaneCameraCapture(world, carla, ego, sinks)
        pipeline = PipelineCapture(client, ego, output, config["selected_case_id"],
                                   required_observations=config.get("required_atoms", []))
        recorder = LaneSourceRecorder(output, ego, overtaken=other)
        frame_map = FrameMap(output / "video_frames.jsonl")
        start = None
        for index in range(config["frames"]):
            target = targets["targets_xy_m"][min(1 + index // 5,
                                                   len(targets["targets_xy_m"]) - 1)]
            _drive(ego, target, carla, engineering)
            if other is not None:
                other.apply_control(carla.VehicleControl(hand_brake=True))
            frame = world.tick()
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError("World snapshot differs from completed Native tick")
            if start is None:
                start = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds - start
            cameras.wait_for_frame(frame)
            waypoint = world.get_map().get_waypoint(ego.get_location())
            if waypoint is None:
                raise ValueError("Native ego left mapped roadway")
            pipeline.capture(frame, time_s)
            recorder.append(frame, time_s, waypoint)
            frame_map.append(frame, time_s)
            frames.append(frame)
        cameras.verify(frames)
    except BaseException as error:
        errors.append(str(error))
        raise
    finally:
        if frame_map is not None:
            frame_map.close()
        if recorder is not None:
            recorder.close()
        if pipeline is not None:
            pipeline.close(confirmed=not errors)
        if cameras is not None:
            cameras.close()
        for sink in sinks.values():
            sink.close()
        for actor in reversed(owned):
            actor.destroy()
        world.apply_settings(original)
        current = world.get_settings()
        restored = (current.synchronous_mode == original.synchronous_mode
                    and current.fixed_delta_seconds == original.fixed_delta_seconds)
        if not restored:
            raise ValueError("Native world settings restoration readback differs")
    if errors or len(frames) != config["frames"]:
        raise ValueError("Native marked-lane capture did not complete")
    (output / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "native", "diagnostic_fixture": False,
        "original_frames": len(frames)}) + "\n")
    seal_capture(output, frames=len(frames), restoration={"restored": restored}, errors=[],
                 encoder_exit_codes={name: 0 for name in CAMERAS},
                 context={"native_map_name": world.get_map().name,
                          "route_road_id": selection["road_id"],
                          "route_lane_id": selection["lane_id"],
                          "route_adjacent_lane_id": selection["adjacent_lane_id"]})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        config = Path("config.json")
        if not config.is_file():
            raise ValueError("Materialized config.json required")
        check_config(json.loads(config.read_text()))
        return
    if not args.output_dir:
        parser.error("--output-dir is required for Native capture")
    run(args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
