"""Exact Native capture proposal for the unaccepted property-bypass case.

`--check` validates the pinned 30-second plan without CARLA. Execution requires
an independently surveyed CARLA map, parcel boundary and signal actor IDs.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import queue
import sys

ROOT = Path(__file__).resolve().parent
CASE = "training__C151707__NRS-484B-307-8e__motor_vehicle_driver__probe_02"
ROAD_CASE = "training__C151707__NRS-484B-307-8e__motor_vehicle_driver__probe_01"
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def check(config):
    require(config["case_id"] in (CASE, ROAD_CASE), "exact case mismatch")
    require(config["law_id"] == "NRS-484B-307-8e" and config["cell_id"] == "C151707"
            and config["actor"] == "motor_vehicle_driver", "exact assignment mismatch")
    require(config["frozen_cell"] == {"layout": "one_way_to_one_way_intersection",
                                       "maneuver": "bypass_signal", "control": "traffic_light"}, "frozen cell changed")
    require(config["rate_hz"] == 20 and config["duration_s"] == 30
            and config["frames"] == 600, "600-frame contract required")
    require(tuple(c["name"] for c in config["cameras"]) == VIEWS, "four source cameras required")
    require(all(c["fps"] == 20 and c["width"] >= 1280 and c["height"] >= 720
                and c.get("pose_strategy")
                and len(c["location_xyz_m"]) == 3 and len(c["rotation_pyr_deg"]) == 3
                for c in config["cameras"]), "camera contract incomplete")
    require(config["physical_completion"] is False and config["legal_verdict"] is None,
            "draft cannot claim physical or legal result")
    require(config["purpose_declaration"] == "avoid_red_signal", "controller purpose changed")
    return {"case_id": CASE, "frames": 600, "rate_hz": 20,
            "source_views": list(VIEWS), "carla_contacted": False,
            "physical_completion": False, "legal_verdict": None}


def read_survey(path):
    survey = json.loads(Path(path).read_text())
    require(survey["source_kind"] == "original_native_property_survey", "original survey required")
    require(survey.get("assignment_id") == CASE.rsplit("__", 1)[0], "survey assignment mismatch")
    require(survey.get("approach_signal_lens_form") == "circular_red_alone" and
            survey.get("approach_signal_facing_source_id"), "surveyed red-alone facing source required")
    require(survey.get("property_id") and survey.get("property_boundary_source_id"),
            "surveyed property authority missing")
    require(survey["map_name"] and survey["property_boundary_source"]
            and survey["approach_lane_source"] and survey["cross_street_lane_source"],
            "map/parcel authority missing")
    require(survey["approach_signal_actor_id"] and survey["cross_signal_actor_id"],
            "signal identity missing")
    require(len(survey["spawn_xyz_yaw_deg"]) == 4 and
            all(len(survey.get(key, [])) >= 3 and all(len(point) == 3 for point in survey[key])
                for key in ("route_xyz_m", "road_only_route_xyz_m")),
            "surveyed property and road-only routes required")
    require(len(survey["property_polygon_xy_m"]) >= 3
            and len(survey["cross_street_polygon_xy_m"]) >= 3
            and all(len(point) == 2 for key in ("property_polygon_xy_m", "cross_street_polygon_xy_m")
                    for point in survey[key]), "survey polygons missing")
    return survey


def inside_polygon(x, y, polygon):
    inside = False
    for i, a in enumerate(polygon):
        b = polygon[(i + 1) % len(polygon)]
        if (a[1] > y) != (b[1] > y):
            crossing = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if x < crossing:
                inside = not inside
    return inside


def control(pose, velocity, target):
    speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
    dx, dy = target[0] - pose.location.x, target[1] - pose.location.y
    distance = math.hypot(dx, dy)
    heading = math.atan2(dy, dx) - math.radians(pose.rotation.yaw)
    heading = math.atan2(math.sin(heading), math.cos(heading))
    steer = max(-0.7, min(0.7, 1.2 * heading))
    target_speed = 4.0 if distance > 3 else 2.0
    throttle = max(0.0, min(0.55, 0.2 + 0.12 * (target_speed - speed)))
    brake = max(0.0, min(1.0, 0.2 * (speed - target_speed)))
    return throttle, brake, steer, speed, distance


def execute(config, output_dir, survey_path, host, port):
    check(config)
    require(survey_path is not None, "original survey required")
    survey = read_survey(survey_path)
    output_root = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
    require(".runtime-work" in output_root, "set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
    require(Path(output_dir).resolve().is_relative_to(Path(output_root).resolve()),
            "Native output must stay under SCENARIO_PIPELINE_OUTPUT_ROOT")
    repo = next((parent for parent in ROOT.parents if (parent / "runtime.py").is_file()), None)
    require(repo is not None, "worker repository root missing")
    sys.path.insert(0, str(repo / "runtime"))
    sys.path.insert(1, str(repo / "runtime" / "python"))
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import restore, snapshot

    output = Path(output_dir)
    if output.exists():
        require((output / "config.json").is_file(), "existing output lacks materialized config")
    else:
        output.mkdir(parents=True)
    (output / "property-survey.json").write_bytes(Path(survey_path).read_bytes())
    (output / "purpose-declaration.json").write_text(json.dumps({
        "source_kind": "original_controller_purpose_declaration",
        "assignment_id": CASE.rsplit("__", 1)[0],
        "declaration_source_id": "native-controller-plan:" + CASE.rsplit("__", 1)[0],
        "declared_purpose": config["purpose_declaration"]}, sort_keys=True) + "\n")
    client = carla.Client(host, port)
    client.set_timeout(15)
    world = client.get_world()
    saved = snapshot(client)
    actors, sensors = [], []
    images = queue.Queue()
    try:
        require(world.get_map().name == survey["map_name"], "survey map differs")
        approach_signal = world.get_actor(int(survey["approach_signal_actor_id"]))
        cross_signal = world.get_actor(int(survey["cross_signal_actor_id"]))
        require(approach_signal is not None and cross_signal is not None
                and approach_signal.type_id.startswith("traffic.traffic_light")
                and cross_signal.type_id.startswith("traffic.traffic_light"),
                "surveyed signal actors missing")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        library = world.get_blueprint_library()
        x, y, z, yaw = survey["spawn_xyz_yaw_deg"]
        ego = world.try_spawn_actor(library.find(config["vehicle_blueprint"]),
                                    carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(yaw=yaw)))
        require(ego is not None, "vehicle spawn occupied")
        actors.append(ego)
        for camera in config["cameras"]:
            blueprint = library.find("sensor.camera.rgb")
            blueprint.set_attribute("image_size_x", str(camera["width"]))
            blueprint.set_attribute("image_size_y", str(camera["height"]))
            blueprint.set_attribute("fov", str(camera["fov_deg"]))
            cx, cy, cz = camera["location_xyz_m"]
            pitch, cyaw, roll = camera["rotation_pyr_deg"]
            sensor = world.spawn_actor(blueprint, carla.Transform(
                carla.Location(x=cx, y=cy, z=cz),
                carla.Rotation(pitch=pitch, yaw=cyaw, roll=roll)), attach_to=ego)
            actors.append(sensor)
            sensors.append(sensor)
            (output / camera["name"]).mkdir()
            sensor.listen(lambda image, name=camera["name"]: images.put((name, image)))
        target_index = 0
        route = survey["road_only_route_xyz_m" if config["case_id"] == ROAD_CASE else "route_xyz_m"]
        with PipelineCapture(client, ego, output, config["case_id"], required_observations=config["required_atoms"]) as capture, \
                FrameMap(output / "video_frames.jsonl") as frame_map, \
                (output / "property-route-native.jsonl").open("x", buffering=1) as trace:
            for frame in range(config["frames"]):
                pose, velocity = ego.get_transform(), ego.get_velocity()
                target = route[target_index]
                throttle, brake, steer, speed, distance = control(pose, velocity, target)
                if distance < 3 and target_index < len(route) - 1:
                    target_index += 1
                ego.apply_control(carla.VehicleControl(throttle=throttle, brake=brake, steer=steer))
                native_frame = world.tick()
                observed_pose, observed_velocity = ego.get_transform(), ego.get_velocity()
                observed_speed = math.sqrt(observed_velocity.x**2 + observed_velocity.y**2 + observed_velocity.z**2)
                body_vertices = [[vertex.x, vertex.y] for vertex in
                                 ego.bounding_box.get_world_vertices(observed_pose)]
                seen = set()
                while len(seen) < 4:
                    name, image = images.get(timeout=15)
                    if image.frame != native_frame or name in seen:
                        continue
                    image.save_to_disk(str(output / name / f"{frame:06d}.png"))
                    seen.add(name)
                capture.capture(native_frame, frame / 20, extra={"video_frame": frame})
                frame_map.append(native_frame, frame / 20,
                                 native_elapsed_s=world.get_snapshot().timestamp.elapsed_seconds)
                trace.write(json.dumps({"source_kind": "original_native_observation",
                                        "frame": frame, "native_frame": native_frame,
                                        "t_s": frame / 20, "vehicle_id": ego.id,
                                        "x_m": observed_pose.location.x, "y_m": observed_pose.location.y,
                                        "body_vertices_xy_m": body_vertices,
                                        "speed_mps": observed_speed, "route_target_index": target_index,
                                        "zone": ("property" if inside_polygon(observed_pose.location.x, observed_pose.location.y, survey["property_polygon_xy_m"])
                                                 else "intersecting_street" if inside_polygon(observed_pose.location.x, observed_pose.location.y, survey["cross_street_polygon_xy_m"])
                                                 else "approach_road"),
                                        "approach_signal_native_state": str(approach_signal.get_state()),
                                        "cross_signal_native_state": str(cross_signal.get_state()),
                                        "approach_signal_actor_id": survey["approach_signal_actor_id"],
                                        "cross_signal_actor_id": survey["cross_signal_actor_id"],
                                        "purpose_declaration": config["purpose_declaration"]}) + "\n")
    finally:
        for sensor in sensors:
            sensor.stop()
        for actor in reversed(actors):
            actor.destroy()
        restore(client, saved)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--property-survey")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    cfg = json.loads((ROOT / "config.json").read_text())
    if args.check:
        print(json.dumps(check(cfg)))
    else:
        require(args.output_dir, "output directory required")
        execute(cfg, args.output_dir, args.property_survey or os.environ.get("SCENARIO_PROPERTY_SURVEY"), args.host, args.port)
