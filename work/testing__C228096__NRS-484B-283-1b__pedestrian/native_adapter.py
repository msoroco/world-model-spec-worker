"""Lazy CARLA acquisition of original curb-entry motion and four cameras."""
from __future__ import annotations

import hashlib
import json
import math
import queue
from pathlib import Path


class NativeAdapter:
    def __init__(self, host: str, port: int, output_dir: Path, scene_plan: dict):
        import carla
        self.carla = carla
        self.client = carla.Client(host, port)
        self.client.set_timeout(30.0)
        self.output_dir = Path(output_dir)
        self.plan = scene_plan
        self.owned = []
        self.sensors = {}
        self.world = None
        self.old_settings = None
        self.frame_rows = []
        self.motion_rows = []

    def open_map(self):
        map_path = Path(self.plan["map_path"])
        data = map_path.read_bytes()
        if hashlib.sha256(data).hexdigest() != self.plan["map_sha256"]:
            raise ValueError("reviewed original OpenDRIVE map changed")
        self.world = self.client.generate_opendrive_world(data.decode("utf-8"))
        self.old_settings = self.world.get_settings()
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        self.world.apply_settings(settings)
        self.map = self.world.get_map()

    def _transform(self, xy):
        location = self.carla.Location(x=xy[0], y=xy[1], z=0)
        waypoint = self.map.get_waypoint(location, project_to_road=True)
        if waypoint is None:
            raise ValueError("source-reviewed spawn has no road elevation")
        location.z = waypoint.transform.location.z + 0.5
        return self.carla.Transform(location, waypoint.transform.rotation)

    def spawn_pedestrian(self, xy):
        blueprints = self.world.get_blueprint_library().filter("walker.pedestrian.*")
        if not blueprints:
            raise ValueError("no Native pedestrian blueprint")
        actor = self.world.try_spawn_actor(blueprints[0], self._transform(xy))
        if actor is None:
            raise ValueError("reviewed pedestrian spawn occupied")
        self.owned.append(actor)
        return actor

    def spawn_vehicle(self, xy):
        blueprints = self.world.get_blueprint_library().filter("vehicle.*")
        if not blueprints:
            raise ValueError("no Native vehicle blueprint")
        actor = self.world.try_spawn_actor(blueprints[0], self._transform(xy))
        if actor is None:
            raise ValueError("reviewed control vehicle spawn occupied")
        self.owned.append(actor)
        return actor

    def set_pedestrian_route(self, actor, points, action, departure_frame):
        self.pedestrian_route = {"actor": actor, "points": points, "next": 1,
                                 "action": action, "departure_frame": departure_frame}

    def set_vehicle_route(self, actor, points, gap_probe):
        self.vehicle_route = {"actor": actor, "points": points, "next": 1,
                              "gap_probe": gap_probe}

    def attach_cameras(self, vehicle):
        for name, profile in self.plan["cameras"].items():
            blueprint = self.world.get_blueprint_library().find("sensor.camera.rgb")
            blueprint.set_attribute("image_size_x", str(profile["width"]))
            blueprint.set_attribute("image_size_y", str(profile["height"]))
            pose = profile["pose"]
            transform = self.carla.Transform(
                self.carla.Location(x=pose["x"], y=pose["y"], z=pose["z"]),
                self.carla.Rotation(pitch=pose["pitch"], yaw=pose["yaw"], roll=pose["roll"]))
            camera = self.world.spawn_actor(blueprint, transform, attach_to=vehicle)
            if camera is None:
                raise ValueError("reviewed camera spawn failed: " + name)
            self.owned.append(camera)
            received = queue.Queue(maxsize=4)
            camera.listen(received.put)
            self.sensors[name] = received

    def _drive(self, route, speed):
        actor = route["actor"]
        points = route["points"]
        location = actor.get_location()
        target = points[route["next"]]
        dx, dy = target[0] - location.x, target[1] - location.y
        distance = math.hypot(dx, dy)
        if distance < 0.5 and route["next"] < len(points) - 1:
            route["next"] += 1
            target = points[route["next"]]
            dx, dy = target[0] - location.x, target[1] - location.y
            distance = math.hypot(dx, dy)
        if distance < 0.5:
            speed = 0.0
        direction = self.carla.Vector3D(dx / distance, dy / distance, 0) if distance else \
            self.carla.Vector3D(0, 0, 0)
        return actor, direction, speed

    def tick_and_capture(self, index: int):
        scene = self.plan["scene"]
        controls = self.plan["motion_controls"]
        pedestrian, direction, speed = self._drive(
            self.pedestrian_route,
            controls["run_speed_mps"] if scene["action"] == "run"
            else controls["walk_speed_mps"])
        if index < self.pedestrian_route["departure_frame"]:
            speed = 0.0
        pedestrian.apply_control(self.carla.WalkerControl(direction=direction, speed=speed))
        vehicle, direction, speed = self._drive(self.vehicle_route,
                                                 controls["vehicle_speed_mps"])
        vehicle.set_target_velocity(self.carla.Vector3D(direction.x * speed,
                                                         direction.y * speed, 0))
        native_frame = self.world.tick()
        camera_frames = {}
        for name, received in self.sensors.items():
            image = received.get(timeout=20.0)
            if image.frame != native_frame:
                raise ValueError("original four-camera frame synchronization failed")
            path = self.output_dir / "capture" / name / f"{index:06d}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            image.save_to_disk(str(path))
            camera_frames[name] = image.frame
        ped_location, veh_location = pedestrian.get_location(), vehicle.get_location()
        ped_velocity, veh_velocity = pedestrian.get_velocity(), vehicle.get_velocity()
        source_fields = {name + "_source_sha256": scene[name + "_source_sha256"]
                         for name in ("pedestrian_motion", "vehicle_motion", "road_boundary",
                                      "curb_safety", "vehicle_path", "driver_control",
                                      "introductory_exceptions") if name + "_source_sha256" in scene}
        source_fields["frame_source_sha256"] = self.plan["map_sha256"]
        source_fields["pedestrian_motion_source_sha256"] = scene["pedestrian_identity_source_sha256"]
        row = {"original_frame": native_frame, "time_s": index / 20,
               "pedestrian_id": str(pedestrian.id), "vehicle_id": str(vehicle.id),
               "action": scene["action"],
               "pedestrian_xy": [ped_location.x, ped_location.y],
               "vehicle_xy": [veh_location.x, veh_location.y],
               "pedestrian_speed_mps": math.sqrt(ped_velocity.x ** 2 + ped_velocity.y ** 2),
               "vehicle_speed_mps": math.sqrt(veh_velocity.x ** 2 + veh_velocity.y ** 2),
               **source_fields}
        self.motion_rows.append(row)
        self.frame_rows.append({"frame": index, "native_frame": native_frame,
                                "time_s": index / 20, "camera_frames": camera_frames})

    def close(self):
        if self.motion_rows:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            (self.output_dir / "original-motion.json").write_text(
                json.dumps({"case_id": self.plan["case_id"], "frames": self.motion_rows}) + "\n",
                encoding="utf-8")
            (self.output_dir / "original-frame-map.json").write_text(
                json.dumps({"source_kind": "original_native_frame_map",
                            "case_id": self.plan["case_id"], "frames": self.frame_rows}) + "\n",
                encoding="utf-8")
        for actor in reversed(self.owned):
            try:
                if hasattr(actor, "stop"):
                    actor.stop()
            finally:
                actor.destroy()
        if self.world is not None and self.old_settings is not None:
            self.world.apply_settings(self.old_settings)

    def destroy(self, actor):
        if actor in self.owned:
            self.owned.remove(actor)
        actor.destroy()
