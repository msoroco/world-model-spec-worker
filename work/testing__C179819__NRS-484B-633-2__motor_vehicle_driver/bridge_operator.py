"""Native CARLA operator for source surveyed elevated-highway geometry.

The reviewed site dossier must provide native_geometry with XODR route
waypoints and sign asset transforms. Missing geometry or a unavailable speed
sign asset fails before recording; the operator never invents a bridge.
"""

from __future__ import annotations

import hashlib
import io
import math
from queue import Empty, Queue


def _point(value, label):
    if not isinstance(value, list) or len(value) != 3 or any(
            not isinstance(x, (int, float)) or isinstance(x, bool) or not math.isfinite(x) for x in value):
        raise ValueError("reviewed native " + label + " world XYZ required")
    return tuple(float(x) for x in value)


def _distance(left, right):
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right)))


class BridgeOperator:
    def __init__(self, client, site, case):
        import carla
        self.carla = carla
        self.client = client
        self.world = client.get_world()
        self.map = self.world.get_map()
        self.site = site
        self.case = case
        self.geometry = site.get("native_geometry")
        if not isinstance(self.geometry, dict):
            raise ValueError("reviewed native bridge route and sign geometry required")
        self.routes = self.geometry.get("route_waypoints")
        self.sign_assets = self.geometry.get("sign_assets")
        if not isinstance(self.routes, dict) or set(self.routes) != {"a_to_b", "b_to_a"}:
            raise ValueError("both reviewed native approach routes required")
        if not isinstance(self.sign_assets, dict) or set(self.sign_assets) != {"end_a", "end_b"}:
            raise ValueError("both reviewed native speed sign assets required")
        self.active_route = self.routes[case["travel_direction_request"]]
        self.sign_readbacks = {}
        self.camera_queues = {}
        self.target_speed_mps = None
        self.ego = None

    def loaded_map_sha256(self):
        return hashlib.sha256(self.map.to_opendrive().encode()).hexdigest()

    def snapshot_settings(self):
        return self.world.get_settings()

    def configure_sync(self, *, rate_hz):
        if rate_hz != 20:
            raise ValueError("original 20 Hz Native capture required")
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / rate_hz
        settings.no_rendering_mode = False
        self.world.apply_settings(settings)

    def readback_sync(self, *, rate_hz):
        settings = self.world.get_settings()
        return (settings.synchronous_mode is True and
                abs(settings.fixed_delta_seconds - 1 / rate_hz) < 1e-8 and
                settings.no_rendering_mode is False)

    def restore_settings(self, settings):
        self.world.apply_settings(settings)

    def readback_restored(self, settings):
        observed = self.world.get_settings()
        return (observed.synchronous_mode == settings.synchronous_mode and
                observed.fixed_delta_seconds == settings.fixed_delta_seconds and
                observed.no_rendering_mode == settings.no_rendering_mode)

    def _waypoint(self, source, label):
        if not isinstance(source, dict) or not all(k in source for k in ("road_id", "lane_id", "s_m", "world_xyz_m")):
            raise ValueError("reviewed native XODR " + label + " required")
        waypoint = self.map.get_waypoint_xodr(int(source["road_id"]), int(source["lane_id"]), float(source["s_m"]))
        if waypoint is None:
            raise ValueError("native XODR waypoint missing: " + label)
        location = waypoint.transform.location
        observed = (location.x, location.y, location.z)
        if _distance(observed, _point(source["world_xyz_m"], label)) > 0.25:
            raise ValueError("reviewed native XODR world position changed: " + label)
        return waypoint

    def read_structure_ends(self, structure_id):
        if structure_id != self.site["structure_id"]:
            raise ValueError("reviewed structure identity differs")
        for direction, route in self.routes.items():
            if not isinstance(route, dict) or set(route) != {"start", "end_a", "end_b", "exit"}:
                raise ValueError("complete reviewed Native route required: " + direction)
            for label, source in route.items():
                self._waypoint(source, direction + ":" + label)
        return (float(self.site["end_a_station_m"]), float(self.site["end_b_station_m"]))

    def spawn_vehicle(self, actor_class, direction, structure_id, *, spawn_adjust_m):
        if actor_class != "motor_vehicle" or direction != self.case["travel_direction_request"] or structure_id != self.site["structure_id"]:
            raise ValueError("Native ego request differs from reviewed bridge case")
        route = self.routes[direction]
        start = route["start"]
        first_end = route["end_a"] if direction == "a_to_b" else route["end_b"]
        travel_sign = 1 if float(first_end["s_m"]) > float(start["s_m"]) else -1
        adjusted = dict(start, s_m=float(start["s_m"]) - travel_sign * spawn_adjust_m)
        waypoint = self.map.get_waypoint_xodr(int(adjusted["road_id"]), int(adjusted["lane_id"]), adjusted["s_m"])
        if waypoint is None:
            raise ValueError("reviewed upstream spawn has no native driving waypoint")
        blueprint_id = self.geometry.get("ego_blueprint_id", "vehicle.lincoln.mkz_2020")
        blueprint = self.world.get_blueprint_library().find(blueprint_id)
        if not blueprint.id.startswith("vehicle."):
            raise ValueError("reviewed ego blueprint is not a motor vehicle")
        if blueprint.has_attribute("role_name"):
            blueprint.set_attribute("role_name", "bridge_exact_ego")
        ego = self.world.try_spawn_actor(blueprint, waypoint.transform)
        if ego is None:
            raise ValueError("reviewed upstream motor vehicle spawn failed")
        self.ego = ego
        return ego

    def read_vehicle_class(self, ego):
        return "motor_vehicle" if ego.id == self.ego.id and ego.type_id.startswith("vehicle.") else "other"

    def set_crossing_route(self, ego, direction, end_a, end_b):
        if ego.id != self.ego.id or direction != self.case["travel_direction_request"]:
            raise ValueError("Native crossing route actor/direction differs")
        if (end_a, end_b) != (float(self.site["end_a_station_m"]), float(self.site["end_b_station_m"])):
            raise ValueError("Native crossing route stationing differs")
        self._waypoint(self.active_route["exit"], "exit")

    def set_target_speed_mps(self, ego, target):
        if ego.id != self.ego.id or not 0 < target < 60:
            raise ValueError("bounded Native target speed required")
        self.target_speed_mps = float(target)

    def spawn_sign(self, end, station, maximum, face):
        asset = self.sign_assets[end]
        if (float(asset.get("station_m", float("nan"))) != station or
                float(asset.get("displayed_maximum_mph", float("nan"))) != maximum or
                asset.get("face_direction") != face):
            raise ValueError("reviewed native speed sign asset differs from Department declaration")
        blueprint_id = asset.get("blueprint_id")
        if not isinstance(blueprint_id, str) or not blueprint_id:
            raise ValueError("reviewed native speed sign blueprint required")
        blueprint = self.world.get_blueprint_library().find(blueprint_id)
        xyz = _point(asset.get("world_xyz_m"), end + " sign")
        rotation = asset.get("rotation_deg")
        if not isinstance(rotation, dict) or set(rotation) != {"pitch", "yaw", "roll"}:
            raise ValueError("reviewed native sign rotation required")
        transform = self.carla.Transform(self.carla.Location(*xyz), self.carla.Rotation(
            pitch=float(rotation["pitch"]), yaw=float(rotation["yaw"]), roll=float(rotation["roll"])))
        actor = self.world.try_spawn_actor(blueprint, transform)
        if actor is None:
            raise ValueError("reviewed original speed sign asset spawn failed")
        self.sign_readbacks[actor.id] = (station, face, xyz)
        return actor

    def read_sign_station_and_face(self, sign):
        station, face, expected = self.sign_readbacks[sign.id]
        location = sign.get_transform().location
        if _distance((location.x, location.y, location.z), expected) > 0.25:
            raise ValueError("spawned sign transform differs from reviewed source")
        return station, face

    def spawn_cameras(self, ego, names, dossier):
        if ego.id != self.ego.id or tuple(names) != ("overview", "approach", "reference_corner", "driver_reference"):
            raise ValueError("four exact original camera views required")
        dimensions = {"overview": (1920, 1080), "approach": (1280, 720),
                      "reference_corner": (1280, 720), "driver_reference": (1280, 720)}
        poses = self.geometry.get("camera_poses")
        if not isinstance(poses, dict) or set(poses) != set(names):
            raise ValueError("reviewed native four-view camera poses required")
        cameras = {}
        for name in names:
            pose = poses[name]
            location = _point(pose.get("location_m"), name + " camera")
            rotation = pose.get("rotation_deg")
            if not isinstance(rotation, dict) or set(rotation) != {"pitch", "yaw", "roll"}:
                raise ValueError("reviewed native camera rotation required")
            blueprint = self.world.get_blueprint_library().find("sensor.camera.rgb")
            width, height = dimensions[name]
            blueprint.set_attribute("image_size_x", str(width))
            blueprint.set_attribute("image_size_y", str(height))
            blueprint.set_attribute("fov", str(pose.get("fov_deg", 90)))
            blueprint.set_attribute("sensor_tick", "0")
            transform = self.carla.Transform(self.carla.Location(*location), self.carla.Rotation(
                pitch=float(rotation["pitch"]), yaw=float(rotation["yaw"]), roll=float(rotation["roll"])))
            camera = self.world.spawn_actor(blueprint, transform, attach_to=ego if pose.get("attach_to_ego") else None)
            queue = Queue(maxsize=8)
            camera.listen(queue.put)
            self.camera_queues[name] = queue
            cameras[name] = camera
        return cameras

    def _control(self):
        if self.target_speed_mps is None or self.ego is None:
            raise ValueError("Native crossing route and speed target missing")
        velocity = self.ego.get_velocity()
        speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
        error = self.target_speed_mps - speed
        waypoint = self.map.get_waypoint(self.ego.get_transform().location)
        if waypoint is None:
            raise ValueError("ego left original mapped highway")
        ahead = waypoint.next(5.0)
        if not ahead:
            raise ValueError("original highway route ends before crossing exit")
        yaw_error = (ahead[0].transform.rotation.yaw - self.ego.get_transform().rotation.yaw + 180) % 360 - 180
        steer = max(-0.35, min(0.35, yaw_error / 45))
        control = self.carla.VehicleControl(throttle=max(0.0, min(0.7, 0.16 * error)),
                                            brake=max(0.0, min(0.6, -0.2 * error)), steer=steer)
        self.ego.apply_control(control)

    def tick_capture(self, index, ego, cameras):
        if ego.id != self.ego.id or set(cameras) != set(self.camera_queues):
            raise ValueError("original Native capture actors changed")
        self._control()
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        if snapshot.frame != frame:
            raise ValueError("original Native world frame differs")
        images = {}
        from PIL import Image
        for name in cameras:
            queue = self.camera_queues[name]
            try:
                image = queue.get(timeout=15)
                while image.frame < frame:
                    image = queue.get(timeout=15)
            except Empty as error:
                raise ValueError("original synchronized camera frame missing: " + name) from error
            if image.frame != frame:
                raise ValueError("original camera frame differs: " + name)
            rgb = Image.frombytes("RGBA", (image.width, image.height), image.raw_data, "raw", "BGRA").convert("RGB")
            stream = io.BytesIO()
            rgb.save(stream, format="PNG")
            images[name] = stream.getvalue()
        waypoint = self.map.get_waypoint(ego.get_transform().location)
        if waypoint is None:
            raise ValueError("original ego has no mapped highway station")
        route = self.active_route
        s_a = float(route["end_a"]["s_m"])
        s_b = float(route["end_b"]["s_m"])
        if abs(s_b - s_a) < 10 or waypoint.road_id != int(route["end_a"]["road_id"]):
            raise ValueError("original elevated structure station projection unavailable")
        station = float(self.site["end_a_station_m"]) + (waypoint.s - s_a) * (
            float(self.site["end_b_station_m"]) - float(self.site["end_a_station_m"])) / (s_b - s_a)
        velocity = ego.get_velocity()
        speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
        return {"index": index, "original_frame": frame,
                "time_s": snapshot.timestamp.elapsed_seconds,
                "ego_station_m": station, "ego_speed_mps": speed,
                "ego_actor_id": ego.id}, images

    def destroy(self, actor):
        if hasattr(actor, "stop") and actor.type_id.startswith("sensor."):
            actor.stop()
        actor.destroy()

    def actor_id(self, actor):
        return actor.id


def make_adapter(client, site, case):
    return BridgeOperator(client, site, case)
