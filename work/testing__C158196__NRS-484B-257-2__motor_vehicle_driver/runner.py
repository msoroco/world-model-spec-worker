"""Exact C158196 subsection 2 Native capture; --check never imports CARLA."""

import argparse
import json
from pathlib import Path
from queue import Empty, Queue

from crossing_drive import apply_tick
from four_camera import CAMERAS, CAMERA_SIZES, FourCameraEncoder
from motion_plan import ASSIGNMENT, validate as validate_motion
from original_crossing_capture import CrossingSourceWriter
from signal_control import SignalControl, find_governing_signal
from site_source import inventory


ROOT = Path(__file__).resolve().parent


def validate_config(config):
    review = validate_motion(ROOT, inventory)
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "NRS-484B-257-2", "C158196", "motor_vehicle_driver"):
        raise ValueError("Wrong exact subsection 2 assignment")
    case_id = config.get("selected_case_id")
    if case_id not in review["case_ids"] or not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("Unselected exact subsection 2 case")
    plan = json.loads((ROOT / "motion-plan.json").read_text())
    row = next(item for item in plan["cases"] if item["case_id"] == case_id)
    if config.get("motion") != row:
        raise ValueError("Config differs from sourced exact motion plan")
    if config.get("required_atoms") != [] or config.get("source_packets") != []:
        raise ValueError("Unsupported Core atom or source packet claim")
    cameras = config.get("cameras")
    if (not isinstance(cameras, list) or [item.get("name") for item in cameras] != list(CAMERAS) or
            any((item.get("width"), item.get("height")) != CAMERA_SIZES[item["name"]]
                or item.get("fov_deg") != 90 for item in cameras)):
        raise ValueError("Four original camera profile differs")
    if set(config.get("camera_mounts", {})) != set(CAMERAS):
        raise ValueError("Four exact camera mounts required")
    if set(config.get("actor_blueprints", {})) != {"ego", "other"}:
        raise ValueError("Two exact vehicle blueprints required")
    return row


def _transform(carla, pose):
    return carla.Transform(carla.Location(**pose["location"]),
                           carla.Rotation(**pose["rotation"]))


def _camera_blueprints(world, config):
    library = world.get_blueprint_library()
    result = {}
    for item in config["cameras"]:
        blueprint = library.find("sensor.camera.rgb")
        blueprint.set_attribute("image_size_x", str(item["width"]))
        blueprint.set_attribute("image_size_y", str(item["height"]))
        blueprint.set_attribute("fov", str(item["fov_deg"]))
        result[item["name"]] = blueprint
    return result


def _capture_world(world, client, output, config, row, carla):
    from pipeline_capture import PipelineCapture

    site = inventory(ROOT / row["site_path"])
    if world.get_map().name != site["native_map_id"]:
        raise ValueError("Native map differs from authored site")
    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 1 / row["rate_hz"]
    world.apply_settings(settings)
    head_road, head_lane = (int(value) for value in site["signal_head_lane_key"].split(":"))
    light = find_governing_signal(world, head_road, head_lane)
    library = world.get_blueprint_library()
    actors, sensors, queues = {}, {}, {}
    encoder_codes = {}
    with SignalControl(world, light, carla.TrafficLightState, row["signal_state"]):
        try:
            for role, position, yaw in (("ego", row["ego_start_xy_m"], 0.0),
                                        ("other", row["other_start_xy_m"], 90.0)):
                blueprint = library.find(config["actor_blueprints"][role])
                blueprint.set_attribute("role_name", "c158196_257_2_" + role)
                transform = carla.Transform(carla.Location(x=position[0], y=position[1], z=0.3),
                                            carla.Rotation(yaw=yaw))
                actor = world.try_spawn_actor(blueprint, transform)
                if actor is None:
                    raise ValueError("Native vehicle spawn failed: " + role)
                actors[role] = actor
            ego_waypoint = world.get_map().get_waypoint(actors["ego"].get_location(), project_to_road=False)
            if ego_waypoint is None or (ego_waypoint.road_id, ego_waypoint.lane_id) != (158190, -1):
                raise ValueError("Ego start differs from signed entrance")
            camera_blueprints = _camera_blueprints(world, config)
            for name in CAMERAS:
                mount = config["camera_mounts"][name]
                attach = mount["attach_to"]
                options = {} if attach is None else {"attach_to": actors[attach]}
                sensor = world.spawn_actor(camera_blueprints[name], _transform(carla, mount["pose"]), **options)
                if sensor is None:
                    raise ValueError("Native camera spawn failed: " + name)
                sensors[name] = sensor
                packet_queue = Queue()
                queues[name] = packet_queue
                sensor.listen(packet_queue.put)
            writer = CrossingSourceWriter(output, site)
            conflict = carla.Location(x=site["conflict_point_xy_m"][0],
                                      y=site["conflict_point_xy_m"][1], z=0.0)
            pipeline = PipelineCapture(client, actors["ego"], output, config["selected_case_id"],
                                       required_observations=config["required_atoms"])
            confirmed = False
            try:
                with FourCameraEncoder(output) as encoder:
                    for tick in range(row["rate_hz"] * row["duration_s"]):
                        apply_tick(actors["ego"], actors["other"], carla.VehicleControl, tick,
                                   hold_ticks=row["ego_hold_ticks"], other_hold_ticks=row["other_hold_ticks"],
                                   ego_throttle=row["ego_throttle"], other_throttle=row["other_throttle"])
                        frame = world.tick()
                        snapshot = world.get_snapshot()
                        if snapshot.frame != frame:
                            raise ValueError("Native snapshot moved after tick")
                        time_s = snapshot.timestamp.elapsed_seconds
                        packets = {}
                        for name in CAMERAS:
                            try:
                                packet = queues[name].get(timeout=10)
                            except Empty as exc:
                                raise ValueError("Missing original camera frame: " + name) from exc
                            if packet.frame != frame or abs(packet.timestamp - time_s) > 1e-3:
                                raise ValueError("Original camera frame or time differs: " + name)
                            packets[name] = packet
                        encoder.validate_packets(packets)
                        writer.add_tick(world, actors["ego"], actors["other"], light,
                                        conflict, frame, time_s, packets)
                        encoder.add_packets(packets)
                        pipeline.capture(frame, time_s)
                    if encoder.count != row["rate_hz"] * row["duration_s"] or writer.count != encoder.count:
                        raise ValueError("Original source frame count differs")
                encoder_codes = dict(encoder.exit_codes)
                confirmed = True
            finally:
                pipeline.close(confirmed=confirmed)
        finally:
            for sensor in reversed(list(sensors.values())):
                try:
                    sensor.stop()
                finally:
                    sensor.destroy()
            for actor in reversed(list(actors.values())):
                actor.destroy()
    return encoder_codes


def capture(config, output_dir, host, port):
    import carla
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import snapshot, restore

    row = validate_config(config)
    output = Path(output_dir).resolve()
    if not output.is_dir() or not (output / "construction.json").is_file():
        raise ValueError("Exact construction must be materialized first")
    client = carla.Client(host, port)
    client.set_timeout(30)
    saved = snapshot(client)
    failure = None
    codes = None
    try:
        world = client.generate_opendrive_world((ROOT / row["site_path"]).read_text())
        codes = _capture_world(world, client, output, config, row, carla)
    except Exception as error:
        failure = error
    try:
        restored = restore(client, saved)
    except Exception as error:
        (output / "native-run-status.json").write_text(json.dumps({"case_id": config["selected_case_id"],
            "capture_sealed": False, "errors": [*([str(failure)] if failure else []),
            "World restoration failed: " + str(error)]}) + "\n")
        raise
    if failure is not None:
        (output / "native-run-status.json").write_text(json.dumps({"case_id": config["selected_case_id"],
            "capture_sealed": False, "errors": [str(failure)]}) + "\n")
        raise failure
    seal_capture(output, frames=row["rate_hz"] * row["duration_s"], restoration=restored,
                 errors=[], encoder_exit_codes=codes,
                 context={"selected_case_id": config["selected_case_id"],
                          "physical_sign_and_highway_review_pending": True})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    config = json.loads((ROOT / "config.json").read_text())
    row = validate_config(config)
    if args.check:
        print(json.dumps({"case_id": row["case_id"], "cpu_config_checked": True,
                          "simulation_started": False}))
        return
    if not args.output_dir:
        raise ValueError("Native capture requires --output-dir")
    capture(config, args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
