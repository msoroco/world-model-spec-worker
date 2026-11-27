"""Lazy CARLA adapter for source-reviewed two-way obstruction construction.

This is an acquisition attempt, not physical or legal acceptance. Local review
must establish lane markings, relative motion, camera pixels and duration.
"""
from __future__ import annotations

import hashlib
import json
import math
import queue
from pathlib import Path


class NativeAdapter:
    def __init__(self, host: str, port: int, output_dir: Path):
        import carla
        self.carla = carla
        self.client = carla.Client(host, port)
        self.client.set_timeout(30.0)
        self.output_dir = Path(output_dir)
        self.owned = []
        self.sensors = {}
        self.old_settings = None
        self.world = None
        self.frame_rows = []
        self.motion_rows = []
        self.relation_rows = []
        self.obstruction_readback = None

    def open_map(self, path: str, expected_sha: str):
        data = Path(path).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected_sha:
            raise ValueError("original reviewed OpenDRIVE map hash changed")
        self.world = self.client.generate_opendrive_world(data.decode("utf-8"))
        self.old_settings = self.world.get_settings()
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        self.world.apply_settings(settings)
        self.map = self.world.get_map()

    def spawn_vehicle(self, role: str, lane_id: str, station_m: float,
                      lateral_offset_m: float, target_speed_mps: float,
                      requested_immediately_behind: bool | None = None):
        road_id = self.site_road_id
        waypoint = self.map.get_waypoint_xodr(int(road_id), int(lane_id), station_m)
        if waypoint is None:
            raise ValueError("reviewed road/lane/station absent in loaded Native map")
        transform = waypoint.transform
        right = transform.get_right_vector()
        transform.location.x += right.x * lateral_offset_m
        transform.location.y += right.y * lateral_offset_m
        transform.location.z += 0.4
        blueprints = self.world.get_blueprint_library().filter("vehicle.*")
        if not blueprints:
            raise ValueError("no local vehicle blueprint")
        blueprint = blueprints[0]
        blueprint.set_attribute("role_name", "nrs484b627_1a_" + role)
        actor = self.world.try_spawn_actor(blueprint, transform)
        if actor is None:
            raise ValueError("source-reviewed vehicle spawn point occupied: " + role)
        self.owned.append(actor)
        yaw = math.radians(transform.rotation.yaw)
        velocity = self.carla.Vector3D(math.cos(yaw) * target_speed_mps,
                                       math.sin(yaw) * target_speed_mps, 0.0)
        actor.set_target_velocity(velocity)
        return actor

    def spawn_obstruction(self, road_id: str, lane_id: str, station_m: float,
                          lateral_edges_m: list[float], blueprint_id: str):
        waypoint = self.map.get_waypoint_xodr(int(road_id), int(lane_id), station_m)
        if waypoint is None:
            raise ValueError("reviewed obstruction station absent in Native map")
        blueprint = self.world.get_blueprint_library().find(blueprint_id)
        if blueprint is None or not blueprint_id.startswith("static.prop."):
            raise ValueError("reviewed physical obstruction blueprint unavailable")
        transform = waypoint.transform
        lateral = sum(lateral_edges_m) / 2
        right = transform.get_right_vector()
        transform.location.x += right.x * lateral
        transform.location.y += right.y * lateral
        transform.location.z += 0.2
        actor = self.world.try_spawn_actor(blueprint, transform)
        if actor is None:
            raise ValueError("physical obstruction spawn failed")
        self.owned.append(actor)
        self.obstruction_readback = {"actor_id": actor.id,
            "blueprint_id": blueprint_id,
            "station_m": station_m,
            "requested_lateral_edges_m": lateral_edges_m,
            "native_world_bounding_box": [
                {"x": point.x, "y": point.y, "z": point.z}
                for point in actor.bounding_box.get_world_vertices(actor.get_transform())]}
        return actor

    def attach_camera(self, name: str, ego, profile: dict):
        blueprint = self.world.get_blueprint_library().find("sensor.camera.rgb")
        blueprint.set_attribute("image_size_x", str(profile["width"]))
        blueprint.set_attribute("image_size_y", str(profile["height"]))
        pose = profile["pose"]
        transform = self.carla.Transform(
            self.carla.Location(x=pose["x"], y=pose["y"], z=pose["z"]),
            self.carla.Rotation(pitch=pose["pitch"], yaw=pose["yaw"], roll=pose["roll"]))
        sensor = self.world.spawn_actor(blueprint, transform, attach_to=ego)
        self.owned.append(sensor)
        received = queue.Queue(maxsize=4)
        sensor.listen(received.put)
        self.sensors[name] = received
        return sensor

    def tick_and_capture(self, frame: int, hz: int, actors: dict, cameras: dict,
                         obstruction, scene: dict):
        if hz != 20:
            raise ValueError("selected capture requires 20 Hz")
        native_frame = self.world.tick()
        images = {}
        for name in cameras:
            image = self.sensors[name].get(timeout=20.0)
            if image.frame != native_frame:
                raise ValueError("four-camera original frame synchronization failed")
            path = self.output_dir / "capture" / name / f"{frame:06d}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            image.save_to_disk(str(path))
            images[name] = str(path)
        states = {}
        reference = self.map.get_waypoint_xodr(int(scene["road_id"]),
                     int(scene["travel_lane_id"]), scene["actors"][0]["station_m"])
        if reference is None:
            raise ValueError("original travel reference lane vanished")
        origin = reference.transform.location
        direction = reference.transform.get_forward_vector()
        right = reference.transform.get_right_vector()
        def projection(point, axis):
            return ((point.x - origin.x) * axis.x +
                    (point.y - origin.y) * axis.y +
                    (point.z - origin.z) * axis.z)
        for role, actor in actors.items():
            location = actor.get_location()
            waypoint = self.map.get_waypoint(location, project_to_road=False)
            if waypoint is None:
                raise ValueError("original actor left reviewed road")
            velocity = actor.get_velocity()
            vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
            lateral = [projection(point, right) for point in vertices]
            forward = [projection(point, direction) for point in vertices]
            states[role] = {"actor_id": actor.id, "road_id": waypoint.road_id,
                            "lane_id": str(waypoint.lane_id), "station_m": waypoint.s,
                            "speed_mps": math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2),
                            "body_left_edge_m": min(lateral), "body_right_edge_m": max(lateral),
                            "body_front_m": max(forward), "body_rear_m": min(forward)}
        ego, follower = states["ego"], states["following_vehicle"]
        same_lane_behind = (ego["road_id"] == follower["road_id"] and
                            ego["lane_id"] == follower["lane_id"] and
                            follower["station_m"] < ego["station_m"])
        obstacle_vertices = obstruction.bounding_box.get_world_vertices(obstruction.get_transform())
        obstacle_lateral = [projection(point, right) for point in obstacle_vertices]
        obstacle_forward = [projection(point, direction) for point in obstacle_vertices]
        relation = {"frame": frame, "time_s": frame / 20,
                    "follower_actor_id": follower["actor_id"],
                    "immediately_behind": same_lane_behind}
        self.relation_rows.append(relation)
        self.motion_rows.append({
            "frame": frame, "time_s": frame / 20,
            "ego_actor_id": ego["actor_id"], "follower_actor_id": follower["actor_id"],
            "ego_lane_id": ego["lane_id"], "follower_lane_id": follower["lane_id"],
            "opposite_lane_id": scene["opposite_lane_id"],
            "one_lane_each_direction_readback": (scene["travel_lane_id"] != scene["opposite_lane_id"]),
            "paved_right_edge_m": scene["paved_right_edge_m"],
            "highway_right_edge_m": scene["highway_right_edge_m"],
            "obstruction_left_edge_m": min(obstacle_lateral),
            "obstruction_right_edge_m": max(obstacle_lateral),
            "obstruction_station_m": scene["obstruction_station_m"],
            "obstruction_forward_edges_m": [min(obstacle_forward), max(obstacle_forward)],
            "ego_body_left_edge_m": ego["body_left_edge_m"],
            "ego_body_right_edge_m": ego["body_right_edge_m"],
            "ego_speed_mps": ego["speed_mps"],
            "follower_speed_mps": follower["speed_mps"],
            "follower_along_route_body_gap_m": max(0.0, ego["body_rear_m"] - follower["body_front_m"]),
            "ego_station_m": ego["station_m"], "follower_station_m": follower["station_m"]})
        row = {"frame": frame, "native_frame": native_frame,
               "time_s": frame / 20,
               "actor_ids": {role: actor.id for role, actor in actors.items()},
               "obstruction_actor_id": obstruction.id,
               "camera_frames": {name: native_frame for name in images}}
        self.frame_rows.append(row)
        with (self.output_dir / "native-frames.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, sort_keys=True) + "\n")

    def close(self):
        if self.frame_rows:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            def save(name, data):
                (self.output_dir / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            save("original-frame-map.json", {"source_kind": "original_native_frame_map",
                "case_id": self.case_id, "frames": self.frame_rows})
            frame_map_sha = hashlib.sha256((self.output_dir / "original-frame-map.json").read_bytes()).hexdigest()
            save("original-motion.json", {"assignment_id": self.assignment_id,
                "case_id": self.case_id, "original_trace_id": self.trace_id,
                "original_frame_map_sha256": frame_map_sha,
                "obstruction_readback": self.obstruction_readback,
                "frames": self.motion_rows})
            save("original-relation.json", {"case_id": self.case_id,
                "source_kind": "original_native_relation",
                "relation_basis_source": "original Native road/lane/station actor readback",
                "samples": self.relation_rows})
        for actor in reversed(self.owned):
            try:
                actor.stop() if hasattr(actor, "stop") else None
            except Exception:
                pass
            actor.destroy()
        if self.world is not None and self.old_settings is not None:
            self.world.apply_settings(self.old_settings)
