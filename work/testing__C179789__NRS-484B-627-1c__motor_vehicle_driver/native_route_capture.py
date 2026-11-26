"""Original CARLA route attempt with owned actors and synchronized camera frames.

The source-reviewed site is checked by runner before this module is imported.
The attempt captures motion; legal impediment and route possibility stay unresolved.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from queue import Queue
import subprocess


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(route_plan: dict, output: Path, host: str, port: int) -> dict:
    import carla

    output.mkdir(parents=True, exist_ok=True)
    if any((output / name).exists() for name in
           ("original-route-motion.json", "video_frames.jsonl", "capture")):
        raise ValueError("original route acquisition output already contains a source")
    client = carla.Client(host, int(port))
    client.set_timeout(30)
    raw_map = Path(route_plan["map_path"]).read_bytes()
    if hashlib.sha256(raw_map).hexdigest() != route_plan["map_sha256"]:
        raise ValueError("reviewed original map hash changed")
    world = client.get_world()
    if hashlib.sha256(world.get_map().to_opendrive().encode("utf-8")).hexdigest() != route_plan["map_sha256"]:
        raise ValueError("Native loaded map differs from source-reviewed OpenDRIVE")
    previous = world.get_settings()
    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 0.05
    actors = []
    cameras = {}
    camera_queues = {}
    rows = []
    frame_maps = []
    body_rows = []
    pipeline = None
    config = json.loads((output / "config.json").read_text())
    try:
        world.apply_settings(settings)
        carla_map = world.get_map()
        library = world.get_blueprint_library()
        vehicle_blueprints = library.filter("vehicle.*")
        if not vehicle_blueprints:
            raise ValueError("no local original vehicle blueprint")
        scene = route_plan["scene"]
        paths = {"ego": scene["main_route_xy"], "follower": scene["follower_route_xy"]}
        vehicles = {}
        for role, points in paths.items():
            start = points[0] if role == "ego" else scene["follower_spawn_xy"]
            location = carla.Location(x=float(start[0]), y=float(start[1]), z=0)
            waypoint = carla_map.get_waypoint(location, project_to_road=False)
            if waypoint is None:
                raise ValueError("source-reviewed vehicle location absent in original map: " + role)
            transform = waypoint.transform
            transform.location.z += 0.4
            blueprint = vehicle_blueprints[0]
            blueprint.set_attribute("role_name", "c179789_" + role)
            actor = world.try_spawn_actor(blueprint, transform)
            if actor is None:
                raise ValueError("original vehicle spawn failed: " + role)
            actors.append(actor)
            vehicles[role] = actor
        camera_blueprint = library.find("sensor.camera.rgb")
        for name in VIEWS:
            profile = route_plan["cameras"][name]
            pose = profile["pose"]
            camera_blueprint.set_attribute("image_size_x", str(profile["width"]))
            camera_blueprint.set_attribute("image_size_y", str(profile["height"]))
            camera_blueprint.set_attribute("fov", str(profile["fov_deg"]))
            transform = carla.Transform(
                carla.Location(x=float(pose["x"]), y=float(pose["y"]), z=float(pose["z"])),
                carla.Rotation(pitch=float(pose["pitch"]), yaw=float(pose["yaw"]), roll=float(pose["roll"])))
            attached = vehicles["ego"] if name == "driver_reference" else None
            sensor = world.spawn_actor(camera_blueprint, transform, attach_to=attached)
            actors.append(sensor)
            received = Queue(maxsize=3)
            sensor.listen(received.put)
            cameras[name] = sensor
            camera_queues[name] = received
        from pipeline_capture import PipelineCapture
        pipeline = PipelineCapture(client, vehicles["ego"], output, route_plan["case_id"])
        for index in range(route_plan["frames"]):
            # This is a route-following engineering controller request, not a realized route claim.
            for role, actor in vehicles.items():
                points = scene[route_plan["requested_route"] + "_route_xy"] if role == "ego" else paths[role]
                location = actor.get_location()
                target = min(points[1:], key=lambda point:
                             (point[0]-location.x)**2 + (point[1]-location.y)**2)
                heading = math.atan2(target[1]-location.y, target[0]-location.x)
                speed = (float(route_plan.get("requested_ego_speed_mps") or 5.0)
                         if role == "ego" else float(config["follower_request_mps"]))
                actor.set_target_velocity(carla.Vector3D(math.cos(heading)*speed,
                                                          math.sin(heading)*speed, 0))
            original_frame = world.tick()
            snapshot = world.get_snapshot()
            if snapshot.frame != original_frame:
                raise ValueError("original tick and snapshot frame differ")
            original_time = snapshot.timestamp.elapsed_seconds
            pipeline.capture(original_frame, original_time)
            camera_frame = {}
            for name in VIEWS:
                image = camera_queues[name].get(timeout=20)
                if image.frame != original_frame:
                    raise ValueError("original four-camera frame join differs")
                destination = output / "capture" / name / f"{index:06d}.png"
                destination.parent.mkdir(parents=True, exist_ok=True)
                image.save_to_disk(str(destination))
                camera_frame[name] = original_frame
            ego = vehicles["ego"]
            follower = vehicles["follower"]
            ego_location = ego.get_location()
            follower_location = follower.get_location()
            ego_waypoint = carla_map.get_waypoint(ego_location, project_to_road=False)
            follower_waypoint = carla_map.get_waypoint(follower_location, project_to_road=False)
            if ego_waypoint is None or follower_waypoint is None:
                raise ValueError("participant left reviewed original road")
            ego_speed = ego.get_velocity().length()
            follower_speed = follower.get_velocity().length()
            gap = ego_location.distance(follower_location)
            route_choice = ("alternate" if ego_waypoint.road_id in scene.get("reviewed_alternate_road_ids", [])
                            else "main")
            rows.append({"original_frame": original_frame, "time_s": original_time,
                         "ego_id": ego.id, "follower_id": follower.id,
                         "ego_xy": [ego_location.x, ego_location.y],
                         "follower_xy": [follower_location.x, follower_location.y],
                         "following_gap_m": gap, "ego_speed_mps": ego_speed,
                         "follower_speed_mps": follower_speed,
                         "ego_route_station_m": ego_waypoint.s,
                         "follower_route_station_m": follower_waypoint.s,
                         "alternate_entry_lead_m": math.dist(
                             (ego_location.x, ego_location.y),
                             tuple(scene["alternate_route_xy"][1])),
                         "actual_route_choice": route_choice,
                         "controlled_access": scene["controlled_access"],
                         "alternate_restriction_state": scene["alternate_restriction_state"],
                         "shared_segment_source_sha256": scene["shared_segment_source_sha256"],
                         "camera_frames": camera_frame})
            frame_maps.append({"video_frame": index, "carla_frame": original_frame,
                               "time_s": original_time})
            vertices = ego.bounding_box.get_world_vertices(ego.get_transform())
            body_rows.append({"frame": original_frame, "time_s": original_time,
                              "body_vertices_m": [[point.x, point.y] for point in vertices],
                              "heading_deg": ego.get_transform().rotation.yaw})
        pipeline.close(confirmed=True)
        pipeline = None
        for name in VIEWS:
            command = ["ffmpeg", "-v", "error", "-framerate", "20", "-i",
                       str(output / "capture" / name / "%06d.png"), "-c:v", "ffv1",
                       str(output / (name + ".mkv"))]
            subprocess.run(command, check=True, capture_output=True, timeout=300)
        (output / "original-route-motion.json").write_text(json.dumps({
            "source_kind": "original_native", "case_id": route_plan["case_id"],
            "site_sha256": route_plan["site_sha256"], "samples": rows}, sort_keys=True) + "\n")
        (output / "video_frames.jsonl").write_text("\n".join(json.dumps(row, sort_keys=True)
            for row in frame_maps) + "\n")
        (output / "body_history.jsonl").write_text("\n".join(json.dumps(row, sort_keys=True)
            for row in body_rows) + "\n")
        return {"frame_count": len(rows), "original_frame_first": rows[0]["original_frame"],
                "original_frame_last": rows[-1]["original_frame"],
                "motion_sha256": sha(output / "original-route-motion.json"),
                "video_frame_map_sha256": sha(output / "video_frames.jsonl"),
                "camera_archives": {name: sha(output / (name + ".mkv")) for name in VIEWS},
                "physical_acceptance": False, "legal_judgment": None}
    finally:
        if pipeline is not None:
            pipeline.close(confirmed=False)
        for actor in reversed(actors):
            try:
                if hasattr(actor, "stop"):
                    actor.stop()
                actor.destroy()
            except Exception:
                pass
        world.apply_settings(previous)
        restored = world.get_settings()
        if (restored.synchronous_mode != previous.synchronous_mode or
                restored.fixed_delta_seconds != previous.fixed_delta_seconds):
            raise ValueError("original Native world settings were not restored")
