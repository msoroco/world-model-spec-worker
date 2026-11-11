"""Native construction probe for C147331; not a delivery recording runner.

It exercises lane selection, spawning, controller and original source capture.
Four-camera capture, Native sealing and saved processing remain separate work.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lane_construction import CASE_SUFFIXES, control_step, route_targets, select_marked_one_way_pair
from lane_sources import LaneSourceRecorder
from lane_camera_capture import CAMERAS, LaneCameraCapture, LosslessSourceSink


def check_config(config):
    case = config.get("selected_case_id", "")
    if not any(case.endswith("__" + suffix) for suffix in CASE_SUFFIXES):
        raise ValueError("Unknown exact lane case")
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "LVMC-11-18-030-B", "C147331", "motor_vehicle_driver"):
        raise ValueError("Lane case law/cell/actor differs")
    if config.get("rate_hz") != 20 or config.get("frames", 0) < 80:
        raise ValueError("Lane construction requires at least 80 frames at 20 Hz")
    if config.get("construction_probe_only") is not True:
        raise ValueError("Construction probe must not masquerade as delivery")
    return case.rsplit("__", 1)[-1]


def _spawn(world, blueprint_id, transform):
    actor = world.try_spawn_actor(world.get_blueprint_library().find(blueprint_id), transform)
    if actor is None:
        raise ValueError("Native lane actor spawn failed: " + blueprint_id)
    return actor


def _drive(actor, target, carla):
    transform = actor.get_transform()
    position = transform.location
    direction = transform.get_forward_vector()
    velocity = actor.get_velocity()
    command = control_step([position.x, position.y], [direction.x, direction.y],
                           [velocity.x, velocity.y], target)
    actor.apply_control(carla.VehicleControl(**command))


def run_probe(config, output, host, port):
    import carla  # Native-only dependency.

    suffix = check_config(config)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    client = carla.Client(host, port)
    client.set_timeout(30.)
    world = client.get_world()
    original = world.get_settings()
    owned = []
    recorder = None
    cameras = None
    sinks = {}
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / config["rate_hz"]
        world.apply_settings(settings)
        selection = select_marked_one_way_pair(world.get_map())
        targets = route_targets(selection, suffix)
        ego = _spawn(world, "vehicle.tesla.model3", selection["primary"][0].transform)
        owned.append(ego)
        other = None
        if targets["overtaken_spawn"] is not None:
            other = _spawn(world, "vehicle.audi.tt", targets["overtaken_spawn"])
            owned.append(other)
        recorder = LaneSourceRecorder(output, ego, overtaken=other)
        for name in CAMERAS:
            sinks[name] = LosslessSourceSink(output, name)
        cameras = LaneCameraCapture(world, carla, ego, sinks)
        observed = []
        for index in range(config["frames"]):
            target = targets["targets_xy_m"][min(1 + index // 5,
                                                   len(targets["targets_xy_m"]) - 1)]
            _drive(ego, target, carla)
            if other is not None:
                other.apply_control(carla.VehicleControl(hand_brake=True))
            frame = world.tick()
            cameras.wait_for_frame(frame)
            snapshot = world.get_snapshot()
            waypoint = world.get_map().get_waypoint(ego.get_location())
            if waypoint is None:
                raise ValueError("Native ego left mapped roadway")
            recorder.append(frame, snapshot.timestamp.elapsed_seconds, waypoint)
            observed.append(frame)
        cameras.verify(observed)
        (output / "construction-probe.json").write_text(json.dumps({
            "format": "worker-lane-construction-probe", "case_id": config["selected_case_id"],
            "road_id": selection["road_id"], "lane_id": selection["lane_id"],
            "adjacent_lane_id": selection["adjacent_lane_id"],
            "frames": observed, "delivery_ready": False}, indent=2) + "\n")
    finally:
        if recorder is not None:
            recorder.close()
        if cameras is not None:
            cameras.close()
        for sink in sinks.values():
            sink.close()
        for actor in reversed(owned):
            actor.destroy()
        world.apply_settings(original)
        if (world.get_settings().synchronous_mode != original.synchronous_mode or
                world.get_settings().fixed_delta_seconds != original.fixed_delta_seconds):
            raise ValueError("Native world settings readback differs after probe")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--output")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    check_config(config)
    if args.run:
        if not args.output:
            raise ValueError("Fresh probe output directory required")
        run_probe(config, args.output, args.host, args.port)


if __name__ == "__main__":
    main()
