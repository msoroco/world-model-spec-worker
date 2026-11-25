"""Lazy CARLA adapter for source-reviewed four-variant construction.

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
                      target_speed_mps: float):
        road_id = self.site_road_id
        waypoint = self.map.get_waypoint_xodr(int(road_id), int(lane_id), station_m)
        if waypoint is None:
            raise ValueError("reviewed road/lane/station absent in loaded Native map")
        transform = waypoint.transform
        transform.location.z += 0.4
        blueprints = self.world.get_blueprint_library().filter("vehicle.*")
        if not blueprints:
            raise ValueError("no local vehicle blueprint")
        blueprint = blueprints[0]
        blueprint.set_attribute("role_name", "nrs484b627_1b_" + role)
        actor = self.world.try_spawn_actor(blueprint, transform)
        if actor is None:
            raise ValueError("source-reviewed vehicle spawn point occupied: " + role)
        self.owned.append(actor)
        yaw = math.radians(transform.rotation.yaw)
        velocity = self.carla.Vector3D(math.cos(yaw) * target_speed_mps,
                                       math.sin(yaw) * target_speed_mps, 0.0)
        actor.set_target_velocity(velocity)
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

    def tick_and_capture(self, frame: int, hz: int, actors: dict, cameras: dict):
        if hz != 20:
            raise ValueError("selected capture requires 20 Hz")
        native_frame = self.world.tick()
        images = {}
        for name, sensor in cameras.items():
            image = self.sensors[name].get(timeout=20.0)
            if image.frame != native_frame:
                raise ValueError("four-camera original frame synchronization failed")
            path = self.output_dir / "capture" / name / f"{frame:06d}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            image.save_to_disk(str(path))
            images[name] = str(path)
        row = {"frame": frame, "native_frame": native_frame, "time_s": frame / 20,
               "actor_ids": {name: actor.id for name, actor in actors.items()},
               "camera_frames": {name: native_frame for name in images}}
        states = {}
        for name, actor in actors.items():
            waypoint = self.map.get_waypoint(actor.get_location(), project_to_road=False)
            if waypoint is None:
                raise ValueError("original actor has left reviewed road")
            velocity = actor.get_velocity()
            states[name] = {"actor_id": actor.id, "road_id": waypoint.road_id,
                            "lane_id": str(waypoint.lane_id), "station_m": waypoint.s,
                            "speed_mps": math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)}
        ego, follower = states["ego"], states["following_vehicle"]
        same_lane_behind = (ego["road_id"] == follower["road_id"] and
                            ego["lane_id"] == follower["lane_id"] and
                            follower["station_m"] < ego["station_m"])
        intermediates = [state for name, state in states.items()
                         if name not in ("ego", "following_vehicle") and
                         state["road_id"] == ego["road_id"] and
                         state["lane_id"] == ego["lane_id"] and
                         follower["station_m"] < state["station_m"] < ego["station_m"]]
        immediately_behind = same_lane_behind and not intermediates
        slower = states.get("slower_vehicle")
        passing = (slower is not None and ego["road_id"] == slower["road_id"] and
                   ego["station_m"] > slower["station_m"])
        self.motion_rows.append({"frame": frame, "time_s": frame / 20,
            "ego_speed_mps": ego["speed_mps"],
            "follower_gap_m": max(0.0, ego["station_m"] - follower["station_m"]),
            "follower_speed_mps": follower["speed_mps"],
            "ego_lane_id": ego["lane_id"],
            "rightmost_same_direction_lane_id": self.rightmost_lane_id,
            "follower_actor_id": follower["actor_id"],
            "follower_lane_id": follower["lane_id"],
            "passing_slower_vehicle_observed": passing,
            "same_direction_marked_lane_count": self.marked_lane_count})
        self.relation_rows.append({"frame": frame, "time_s": frame / 20,
            "follower_actor_id": follower["actor_id"],
            "immediately_behind": immediately_behind})
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
            save("original-motion.json", {"assignment_id": self.assignment_id,
                "case_id": self.case_id, "original_trace_id": self.trace_id,
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
