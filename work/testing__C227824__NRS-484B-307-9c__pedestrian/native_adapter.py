"""Lazy CARLA acquisition of source-reviewed red/arrow signal and pedestrian entry."""
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
            raise ValueError("reviewed original OpenDRIVE changed")
        self.world = self.client.generate_opendrive_world(data.decode("utf-8"))
        self.old_settings = self.world.get_settings()
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        self.world.apply_settings(settings)
        self.map = self.world.get_map()
        asset_ids = self.plan["native_signal_assets"]
        self.signals = {}
        for name, actor_id in asset_ids.items():
            actor = self.world.get_actor(actor_id)
            if actor is None or not hasattr(actor, "set_state") or not hasattr(actor, "get_state"):
                raise ValueError("reviewed Native signal asset unavailable: " + name)
            self.signals[name] = actor
        self.signal_states_before = {name: actor.get_state() for name, actor in self.signals.items()}

    def _transform(self, xy):
        location = self.carla.Location(x=xy[0], y=xy[1], z=0)
        waypoint = self.map.get_waypoint(location, project_to_road=True)
        if waypoint is None:
            raise ValueError("reviewed pedestrian spawn has no road elevation")
        location.z = waypoint.transform.location.z + 0.5
        return self.carla.Transform(location, waypoint.transform.rotation)

    def spawn_pedestrian(self, xy):
        blueprints = self.world.get_blueprint_library().filter("walker.pedestrian.*")
        if not blueprints:
            raise ValueError("no Native pedestrian blueprint")
        transform = self._transform(xy)
        signal = self.plan["scene"]["signal_facing_xy"]
        transform.rotation.yaw = math.degrees(math.atan2(signal[1] - xy[1], signal[0] - xy[0]))
        actor = self.world.try_spawn_actor(blueprints[0], transform)
        if actor is None:
            raise ValueError("reviewed pedestrian spawn occupied")
        self.owned.append(actor)
        return actor

    def set_official_signal(self, steady_red, green_turn_arrow):
        if steady_red is not True or green_turn_arrow is not True:
            raise ValueError("exact red plus green turn arrow required")
        self.signals["red_signal_actor_id"].set_state(self.carla.TrafficLightState.Red)
        self.signals["green_arrow_actor_id"].set_state(self.carla.TrafficLightState.Green)

    def set_other_device(self, display):
        if display not in ("none", "walk"):
            raise ValueError("unreviewed other device display")
        state = self.carla.TrafficLightState.Green if display == "walk" else self.carla.TrafficLightState.Off
        self.signals["other_device_actor_id"].set_state(state)

    def set_pedestrian_route(self, pedestrian, route, movement):
        if movement not in ("enter", "wait"):
            raise ValueError("unreviewed pedestrian movement")
        self.pedestrian_route = {"actor": pedestrian, "points": route, "next": 1,
                                 "movement": movement}

    def attach_cameras(self, pedestrian):
        for name, profile in self.plan["cameras"].items():
            blueprint = self.world.get_blueprint_library().find("sensor.camera.rgb")
            blueprint.set_attribute("image_size_x", str(profile["width"]))
            blueprint.set_attribute("image_size_y", str(profile["height"]))
            pose = profile["pose"]
            transform = self.carla.Transform(
                self.carla.Location(x=pose["x"], y=pose["y"], z=pose["z"]),
                self.carla.Rotation(pitch=pose["pitch"], yaw=pose["yaw"], roll=pose["roll"]))
            camera = self.world.spawn_actor(blueprint, transform, attach_to=pedestrian)
            if camera is None:
                raise ValueError("reviewed camera spawn failed: " + name)
            self.owned.append(camera)
            received = queue.Queue(maxsize=4)
            camera.listen(received.put)
            self.sensors[name] = received

    def _direction(self):
        route = self.pedestrian_route
        actor = route["actor"]
        target = route["points"][route["next"]]
        location = actor.get_location()
        dx, dy = target[0] - location.x, target[1] - location.y
        distance = math.hypot(dx, dy)
        if distance < 0.5 and route["next"] < len(route["points"]) - 1:
            route["next"] += 1
            target = route["points"][route["next"]]
            dx, dy = target[0] - location.x, target[1] - location.y
            distance = math.hypot(dx, dy)
        direction = self.carla.Vector3D(dx / distance, dy / distance, 0) if distance else self.carla.Vector3D(0, 0, 0)
        return direction, distance

    def _signed_boundary(self, actor):
        scene = self.plan["scene"]
        a, b = scene["highway_boundary_line_xy"]
        dx, dy = b[0] - a[0], b[1] - a[1]
        norm = math.hypot(dx, dy)
        if norm <= 0:
            raise ValueError("reviewed highway boundary segment degenerate")
        vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
        signed = [scene["inside_sign"] * (dx * (point.y - a[1]) - dy * (point.x - a[0])) / norm
                  for point in vertices]
        return max(signed)

    def tick_and_capture(self, index: int):
        scene = self.plan["scene"]
        pedestrian = self.pedestrian_route["actor"]
        direction, distance = self._direction()
        speed = self.plan["motion_controls"]["walk_speed_mps"] if self.pedestrian_route["movement"] == "enter" and distance >= 0.5 and index >= 100 else 0.0
        pedestrian.apply_control(self.carla.WalkerControl(direction=direction, speed=speed))
        native_frame = self.world.tick()
        expected = {"red_signal_actor_id": self.carla.TrafficLightState.Red,
                    "green_arrow_actor_id": self.carla.TrafficLightState.Green,
                    "other_device_actor_id": self.carla.TrafficLightState.Green if scene["other_device_display"] == "walk" else self.carla.TrafficLightState.Off}
        if any(self.signals[name].get_state() != state for name, state in expected.items()):
            raise ValueError("original concurrent signal or other-device display changed")
        camera_frames = {}
        for name, received in self.sensors.items():
            image = received.get(timeout=20.0)
            if image.frame != native_frame:
                raise ValueError("original four-camera frame synchronization failed")
            path = self.output_dir / "capture" / name / f"{index:06d}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            image.save_to_disk(str(path))
            camera_frames[name] = image.frame
        source = {name + "_sha256": scene[name + "_source_sha256"] for name in
                  ("highway_boundary", "facing_orientation", "other_device_display")}
        source.update({"source_sha256": self.plan["map_sha256"],
                       "pedestrian_body_sha256": scene["person_afoot_source_sha256"],
                       "pedestrian_motion_sha256": scene["pedestrian_route_source_sha256"],
                       "signal_display_sha256": scene["red_arrow_timing_source_sha256"],
                       "highway_boundary_source_sha256": scene["highway_boundary_source_sha256"]})
        row = {"original_frame": native_frame, "time_s": index / 20,
               "pedestrian_id": str(pedestrian.id),
               "person_afoot": pedestrian.type_id.startswith("walker.pedestrian."),
               "facing_signal": self._faces_signal(pedestrian),
               "official_steady_red": self.signals["red_signal_actor_id"].get_state() == self.carla.TrafficLightState.Red,
               "official_green_turn_arrow": self.signals["green_arrow_actor_id"].get_state() == self.carla.TrafficLightState.Green,
               "other_device_display": scene["other_device_display"],
               "body_nearest_signed_boundary_m": self._signed_boundary(pedestrian),
               "pedestrian_xy": [pedestrian.get_location().x, pedestrian.get_location().y],
               **source}
        self.motion_rows.append(row)
        self.frame_rows.append({"frame": index, "native_frame": native_frame,
                                "time_s": index / 20, "camera_frames": camera_frames})

    def _faces_signal(self, actor):
        location = actor.get_location()
        signal = self.plan["scene"]["signal_facing_xy"]
        dx, dy = signal[0] - location.x, signal[1] - location.y
        distance = math.hypot(dx, dy)
        if distance <= 0:
            return False
        forward = actor.get_transform().get_forward_vector()
        return (forward.x * dx + forward.y * dy) / distance >= 0.7

    def close(self):
        if self.motion_rows:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            (self.output_dir / "original-motion.json").write_text(
                json.dumps({"case_id": self.plan["case_id"], "frames": self.motion_rows}) + "\n", encoding="utf-8")
            (self.output_dir / "original-frame-map.json").write_text(
                json.dumps({"source_kind": "original_native_frame_map", "case_id": self.plan["case_id"],
                            "frames": self.frame_rows}) + "\n", encoding="utf-8")
        for actor in reversed(self.owned):
            try:
                if hasattr(actor, "stop"):
                    actor.stop()
            finally:
                actor.destroy()
        if self.world is not None:
            if hasattr(self, "signal_states_before"):
                for name, state in self.signal_states_before.items():
                    self.signals[name].set_state(state)
            if self.old_settings is not None:
                self.world.apply_settings(self.old_settings)

    def destroy(self, actor):
        if actor in self.owned:
            self.owned.remove(actor)
        actor.destroy()
