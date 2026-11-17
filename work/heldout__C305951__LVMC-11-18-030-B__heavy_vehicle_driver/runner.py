"""Native heavy-vehicle marked-lane capture; CARLA is imported only in run()."""

from __future__ import annotations

import argparse
import json
from math import atan2, hypot, isfinite, pi
from pathlib import Path

from heavy_lane_camera import CAMERAS, HeavyLaneCameraCapture, LosslessSourceSink
from heavy_lane_source import HeavyLaneSourceRecorder, save_three_lane_survey, select_three_lane_site


CASE = "heldout__C305951__LVMC-11-18-030-B__heavy_vehicle_driver__within_marked_lane"
PACKAGE_SUFFIXES = (
    "within_marked_lane", "unexcused_boundary_crossing",
    "passing_boundary_crossing", "lawful_turn_preparation_boundary_crossing",
    "heavy_passing_plan-0000", "heavy_passing_plan-0001",
    "heavy_passing_plan-0002", "heavy_turn_plan-0000",
    "heavy_turn_plan-0001", "heavy_turn_plan-0002",
)
PACKAGE_CASES = [CASE.rsplit("__", 1)[0] + "__" + name for name in PACKAGE_SUFFIXES]


def check_config(config):
    if (config.get("selected_case_id"), config.get("law_id"), config.get("cell_id"),
            config.get("actor")) != (CASE, "LVMC-11-18-030-B", "C305951", "heavy_vehicle_driver"):
        raise ValueError("Exact heavy marked-lane identity mismatch")
    if config.get("supported_case_ids") != PACKAGE_CASES:
        raise ValueError("Heavy marked-lane package case inventory differs")
    if (config.get("rate_hz"), config.get("frames"), config.get("duration_s")) != (20, 160, 8):
        raise ValueError("Original 20 Hz, eight-second timing required")
    if config.get("case", {}).get("case_id") != CASE or not isinstance(
            config["case"].get("recording_description"), dict):
        raise ValueError("Exact case recording description missing")
    cameras = config.get("cameras")
    if not isinstance(cameras, list) or len(cameras) != 4:
        raise ValueError("Four named source cameras required")
    expected = [(name, *profile[2], profile[3]) for name, profile in CAMERAS.items()]
    actual = [(row.get("name"), row.get("width"), row.get("height"), row.get("fov_deg"))
              for row in cameras]
    if actual != expected or any(not row.get("pose_strategy") for row in cameras):
        raise ValueError("Original camera profile mismatch")
    engineering = config.get("engineering", {})
    if set(engineering) != {"heavy_blueprint", "route_step_m", "target_speed_mps",
                            "spawn_height_offset_m"}:
        raise ValueError("Heavy Native construction knobs missing")
    if engineering["heavy_blueprint"] != "vehicle.carlamotors.carlacola":
        raise ValueError("First exact case requires measured heavy truck blueprint")
    for key in ("route_step_m", "target_speed_mps", "spawn_height_offset_m"):
        value = engineering[key]
        if not isinstance(value, (int, float)) or not isfinite(value) or value <= 0:
            raise ValueError("Invalid heavy Native construction knob: " + key)
    return config


def route_from_site(origin, *, step_m, count=50):
    route = [origin]
    for _ in range(count - 1):
        options = [wp for wp in route[-1].next(step_m)
                   if int(wp.road_id) == int(origin.road_id)
                   and int(wp.lane_id) == int(origin.lane_id)]
        if not options:
            raise ValueError("Heavy vehicle route left surveyed marked lane")
        route.append(sorted(options, key=lambda wp: float(getattr(wp, "s", 0)))[0])
    return route


def control_step(actor, target, target_speed_mps):
    transform = actor.get_transform()
    location = transform.location
    forward = transform.get_forward_vector()
    velocity = actor.get_velocity()
    tx, ty = target.transform.location.x - location.x, target.transform.location.y - location.y
    desired = atan2(ty, tx)
    heading = atan2(forward.y, forward.x)
    error = (desired - heading + pi) % (2 * pi) - pi
    speed = hypot(velocity.x, velocity.y)
    return {"throttle": max(0., min(.6, .3 * (target_speed_mps - speed))),
            "brake": max(0., min(.5, .3 * (speed - target_speed_mps))),
            "steer": max(-.45, min(.45, .7 * error))}


def run(output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture

    output = Path(output_dir)
    config = check_config(json.loads((output / "config.json").read_text()))
    engineering = config["engineering"]
    client = carla.Client(host, port)
    client.set_timeout(30.)
    world = client.get_world()
    original = world.get_settings()
    owned, sinks, frames, errors = [], {}, [], []
    cameras = pipeline = recorder = frame_map = None
    restored = False
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / config["rate_hz"]
        world.apply_settings(settings)
        native_map = world.get_map()
        origin, survey = select_three_lane_site(native_map,
                                                spacing_m=engineering["route_step_m"])
        route = route_from_site(origin, step_m=engineering["route_step_m"])
        survey_sha = save_three_lane_survey(output / "native_three_lane_survey.json", survey)
        spawn = origin.transform
        spawn.location.z += engineering["spawn_height_offset_m"]
        blueprint = world.get_blueprint_library().find(engineering["heavy_blueprint"])
        ego = world.try_spawn_actor(blueprint, spawn)
        if ego is None:
            raise ValueError("Native heavy-vehicle spawn failed")
        owned.append(ego)
        for name in CAMERAS:
            sinks[name] = LosslessSourceSink(output, name)
        cameras = HeavyLaneCameraCapture(world, carla, ego, sinks)
        pipeline = PipelineCapture(client, ego, output, CASE,
                                   required_observations=config.get("required_atoms", []))
        recorder = HeavyLaneSourceRecorder(output, [ego],
                                           survey_path=output / "native_three_lane_survey.json",
                                           survey_sha256=survey_sha)
        frame_map = FrameMap(output / "video_frames.jsonl")
        start = None
        for index in range(config["frames"]):
            target = route[min(1 + index // 5, len(route) - 1)]
            ego.apply_control(carla.VehicleControl(**control_step(
                ego, target, engineering["target_speed_mps"])))
            frame = world.tick()
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError("Native heavy-vehicle tick/snapshot mismatch")
            if start is None:
                start = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds - start
            cameras.wait_for_frame(frame)
            waypoint = native_map.get_waypoint(ego.get_location())
            if waypoint is None:
                raise ValueError("Heavy vehicle left Native road")
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
        raise ValueError("Native heavy-vehicle capture incomplete")
    (output / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "native", "diagnostic_fixture": False,
        "original_frames": len(frames), "survey_sha256": survey_sha}) + "\n")
    seal_capture(output, frames=len(frames), restoration={"restored": restored}, errors=[],
                 encoder_exit_codes={name: 0 for name in CAMERAS},
                 context={"native_map_name": native_map.name,
                          "route_road_id": survey["route_road_id"],
                          "route_lane_id": survey["subject_lane_id"]})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        check_config(json.loads(Path(__file__).with_name("config.json").read_text()))
    elif args.output_dir:
        run(args.output_dir, args.host, args.port)
    else:
        parser.error("--output-dir required for Native capture")


if __name__ == "__main__":
    main()
