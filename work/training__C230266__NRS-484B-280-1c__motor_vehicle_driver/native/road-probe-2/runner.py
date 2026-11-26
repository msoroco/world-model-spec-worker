"""Unselected Native road-pedestrian capture proposal for exact probe 1."""

import argparse
import json
import math
import queue
from pathlib import Path

CASE = "training__C230266__NRS-484B-280-1c__motor_vehicle_driver__probe_2"
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def require(value, message):
    if not value:
        raise ValueError(message)


def check(config):
    require(config.get("case_id") == CASE and config.get("law_id") == "NRS-484B-280-1c"
            and config.get("cell_id") == "C230266"
            and config.get("actor") == "motor_vehicle_driver", "Wrong exact assignment")
    require(config.get("frozen_cell") == {"layout": "road", "maneuver": "travel",
                                          "control": "pedestrian"}, "Frozen cell changed")
    require(config.get("rate_hz") == 20 and config.get("duration_s") == 30
            and config.get("frames") == 600, "Full 600-frame window required")
    cameras = config.get("cameras")
    require(isinstance(cameras, list) and tuple(c.get("name") for c in cameras) == VIEWS,
            "Four named source cameras required")
    require(cameras[0].get("width") == 1920 and cameras[0].get("height") == 1080,
            "Overview resolution changed")
    for camera in cameras:
        require(camera.get("fps") == 20 and camera.get("width", 0) >= 1280
                and camera.get("height", 0) >= 720
                and len(camera.get("location_xyz_m", [])) == 3
                and len(camera.get("rotation_pyr_deg", [])) == 3,
                "Camera rate, resolution or pose missing")
    require(config.get("physical_completion") is False and config.get("legal_verdict") is None,
            "Draft may not claim physical or legal outcome")
    require(config.get("controller") == "maintain_approach_request"
            and config.get("road_survey_required") is True
            and config.get("driver_observation_not_inferred_from_visibility") is True,
            "Source and controller policy changed")
    return {"case_id": CASE, "frames": 600, "rate_hz": 20,
            "source_views": list(VIEWS), "carla_contacted": False,
            "physical_completion": False, "legal_verdict": None}


def read_survey(path):
    source = json.loads(Path(path).read_text())
    require(source.get("source_kind") == "original_native_road_survey"
            and source.get("map_name") and source.get("road_boundary_source")
            and source.get("vehicle_spawn_index") is not None
            and len(source.get("pedestrian_spawn_xyz_m", [])) == 3
            and source.get("pedestrian_classification_source")
            and source.get("control_relationship_source"), "Original road and pedestrian survey missing")
    return source


def control(distance_m, speed_mps):
    require(math.isfinite(distance_m) and math.isfinite(speed_mps)
            and speed_mps >= 0, "Measured distance and speed required")
    if False and distance_m < 18:
        return {"throttle": 0.0, "brake": 0.45, "phase": "slow_request"}
    return {"throttle": 0.22, "brake": 0.0, "phase": "approach_request"}


def execute(config, output_dir, survey_path, host, port):
    check(config)
    require(survey_path is not None, "Original road survey required")
    source = read_survey(survey_path)
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import restore, snapshot

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    client = carla.Client(host, port)
    client.set_timeout(15)
    world = client.get_world()
    original = snapshot(client)
    actors, sensors = [], []
    images = queue.Queue()
    try:
        require(world.get_map().name == source["map_name"], "Road survey map differs")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        spawns = world.get_map().get_spawn_points()
        require(0 <= source["vehicle_spawn_index"] < len(spawns), "Vehicle spawn unavailable")
        ego = world.try_spawn_actor(world.get_blueprint_library().find(config["vehicle_blueprint"]),
                                    spawns[source["vehicle_spawn_index"]])
        require(ego is not None, "Vehicle spawn occupied")
        actors.append(ego)
        x, y, z = source["pedestrian_spawn_xyz_m"]
        ped = world.try_spawn_actor(world.get_blueprint_library().find(config["pedestrian_blueprint"]),
                                    carla.Transform(carla.Location(x=x, y=y, z=z)))
        require(ped is not None, "Pedestrian spawn occupied")
        actors.append(ped)
        for camera in config["cameras"]:
            bp = world.get_blueprint_library().find("sensor.camera.rgb")
            bp.set_attribute("image_size_x", str(camera["width"]))
            bp.set_attribute("image_size_y", str(camera["height"]))
            bp.set_attribute("fov", str(camera["fov_deg"]))
            cx, cy, cz = camera["location_xyz_m"]
            pitch, yaw, roll = camera["rotation_pyr_deg"]
            sensor = world.spawn_actor(bp, carla.Transform(carla.Location(x=cx, y=cy, z=cz),
                                                             carla.Rotation(pitch=pitch, yaw=yaw, roll=roll)),
                                       attach_to=ego)
            actors.append(sensor)
            sensors.append(sensor)
            (output / camera["name"]).mkdir()
            sensor.listen(lambda image, name=camera["name"]: images.put((name, image)))
        with PipelineCapture(client, ego, output, CASE,
                             required_observations=config["required_atoms"]) as capture, \
                FrameMap(output / "video_frames.jsonl") as frame_map, \
                (output / "pedestrian-caution-trace.jsonl").open("x", buffering=1) as trace:
            for frame in range(600):
                pose = ego.get_transform()
                ped_pose = ped.get_transform()
                velocity = ego.get_velocity()
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                distance = math.hypot(ped_pose.location.x - pose.location.x,
                                      ped_pose.location.y - pose.location.y)
                request = control(distance, speed)
                ego.apply_control(carla.VehicleControl(throttle=request["throttle"],
                                                       brake=request["brake"], steer=0.0))
                native_frame = world.tick()
                seen = set()
                while len(seen) < 4:
                    name, image = images.get(timeout=15)
                    if image.frame != native_frame or name in seen:
                        continue
                    image.save_to_disk(str(output / name / f"{frame:06d}.png"))
                    seen.add(name)
                capture.capture(native_frame, frame / 20, extra={"video_frame": frame,
                                                                  "pedestrian_actor_id": ped.id})
                frame_map.append(native_frame, frame / 20,
                                 native_elapsed_s=world.get_snapshot().timestamp.elapsed_seconds)
                trace.write(json.dumps({"source_kind": "original_native_observation",
                                        "frame": frame, "native_frame": native_frame,
                                        "video_frame": frame, "time_s": frame / 20,
                                        "ego_x_m": pose.location.x, "ego_y_m": pose.location.y,
                                        "ped_x_m": ped_pose.location.x,
                                        "ped_y_m": ped_pose.location.y,
                                        "ego_speed_mps": speed,
                                        "driver_observed_pedestrian": None,
                                        "driver_observation_source": None,
                                        "line_of_sight_clear": None,
                                        "requested_control": request}) + "\n")
    finally:
        for sensor in sensors:
            sensor.stop()
        for actor in reversed(actors):
            actor.destroy()
        restore(client, original)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--road-survey")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    cfg = json.loads(Path("config.json").read_text())
    if args.check:
        print(json.dumps(check(cfg)))
    else:
        require(args.output_dir, "Output directory required")
        execute(cfg, args.output_dir, args.road_survey, args.host, args.port)
