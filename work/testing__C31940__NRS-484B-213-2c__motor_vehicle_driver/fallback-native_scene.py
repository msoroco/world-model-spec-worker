"""Reviewed original bridge-approach CARLA construction and route controller."""
from __future__ import annotations

import hashlib
import math

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CAMERA_SIZES = ((1920, 1080), (1280, 720), (1280, 720), (1280, 720))
ASSIGNMENT = "testing__C31940__NRS-484B-213-2c__motor_vehicle_driver"
CASE_VARIANTS = {"obstructed_beyond_100ft", "obstructed_at_100ft",
                 "obstructed_within_100ft", "clear_within_100ft",
                 "right_side_within_100ft", "one_way_exception"}


def require(value, message):
    if not value:
        raise ValueError(message)


def vector(values, length, label):
    require(isinstance(values, list) and len(values) == length and
            all(type(v) in (float, int) and math.isfinite(v) for v in values),
            "reviewed " + label + " coordinates required")
    return values


def validate(packet, case_id):
    variant = case_id.removeprefix(ASSIGNMENT + "__")
    require(case_id.startswith(ASSIGNMENT + "__") and variant in CASE_VARIANTS and
            packet.get("case_id") == case_id, "exact bridge case mismatch")
    require(packet.get("law_id") == "NRS-484B-213-2c" and
            packet.get("cell_id") == "C31940" and
            packet.get("actor") == "motor_vehicle_driver", "scope mismatch")
    require(packet.get("reviewed") is True and packet.get("reviewer") and
            packet.get("review_source_sha256"), "separate original bridge review required")
    require(packet.get("map_opendrive_sha256") and packet.get("fps") == 20 and
            type(packet.get("duration_s")) is int and packet["duration_s"] >= 20,
            "reviewed OpenDRIVE and 20 Hz duration required")
    road = packet.get("road", {})
    require(road.get("public_highway") is True and road.get("structure_type") == "bridge" and
            road.get("bridge_source_sha256") and road.get("centerline_source_sha256") and
            type(road.get("bridge_entrance_station_m")) in (int, float),
            "reviewed bridge, entrance and highway authority required")
    one_way = road.get("one_way_highway")
    require(one_way in (True, False), "reviewed one-way status required")
    require(one_way == (variant == "one_way_exception"), "case highway direction mismatch")
    lanes = road.get("lanes")
    require(isinstance(lanes, list) and len(lanes) >= 2 and
            all(item.get("lane_id") and item.get("direction") in (1, -1) for item in lanes),
            "reviewed lane directions required")
    directions = {item["direction"] for item in lanes}
    require(directions == ({1} if one_way else {1, -1}),
            "one-way exception or opposing lane direction mismatch")
    axis = vector(road.get("forward_unit_xy"), 2, "forward route axis")
    require(abs(math.hypot(*axis)-1) <= .01, "reviewed forward axis not unit length")
    vector(road.get("centerline_origin_xy"), 2, "centerline origin")
    actors = packet.get("actors")
    require(isinstance(actors, dict) and set(actors) == {"ego"},
            "one original ego vehicle required")
    ego = actors["ego"]
    require(str(ego.get("blueprint", "")).startswith("vehicle.") and
            ego.get("direction") == 1 and ego.get("source_sha256"),
            "reviewed ego vehicle and direction required")
    vector(ego.get("pose"), 6, "ego pose")
    route = ego.get("route")
    require(isinstance(route, list) and len(route) >= 2, "reviewed ego route required")
    for point in route:
        vector(point, 3, "ego route point")
    progress = (route[-1][0]-route[0][0])*axis[0] + (route[-1][1]-route[0][1])*axis[1]
    require(progress > 5, "ego route not approaching bridge")
    heading = math.radians(ego["pose"][4])
    require((route[-1][0]-route[0][0])*math.cos(heading) +
            (route[-1][1]-route[0][1])*math.sin(heading) > 5,
            "ego heading contradicts bridge approach")
    require(type(ego.get("target_speed_mps")) in (int, float) and
            0 < ego["target_speed_mps"] < 50, "reviewed ego speed required")
    half_length = ego.get("reviewed_body_half_length_m")
    require(type(half_length) in (int, float) and 0.5 < half_length < 5 and
            ego.get("body_dimensions_source_sha256"),
            "reviewed ego body length and source required")
    start_center_station = ((ego["pose"][0]-road["centerline_origin_xy"][0])*axis[0] +
                            (ego["pose"][1]-road["centerline_origin_xy"][1])*axis[1])
    start_front_gap_m = road["bridge_entrance_station_m"]-(start_center_station+half_length)
    requested = {"obstructed_beyond_100ft": 30.7848,
                 "obstructed_at_100ft": 30.48}.get(variant, 30.1752)
    require(abs(start_front_gap_m-requested) <= .05,
            "reviewed front body edge misses selected 100-foot probe")
    origin = road["centerline_origin_xy"]
    laterals = [-(point[0]-origin[0])*axis[1]+(point[1]-origin[1])*axis[0]
                for point in route]
    require((max(laterals) <= 0 if variant == "right_side_within_100ft"
             else max(laterals) > 0.5),
            "reviewed route does not construct selected left-side position")
    if variant != "clear_within_100ft":
        blocker = packet.get("opaque_blocker")
        require(isinstance(blocker, dict) and blocker.get("blueprint") and
                blocker.get("source_sha256") and blocker.get("ray_intersection_plan"),
                "physical opaque view blocker required")
        vector(blocker.get("pose"), 6, "opaque blocker pose")
    cameras = packet.get("cameras")
    require(isinstance(cameras, dict) and set(cameras) == set(CAMERAS),
            "four reviewed camera poses required")
    for name, size in zip(CAMERAS, CAMERA_SIZES):
        camera = cameras[name]
        vector(camera.get("pose"), 6, name + " camera pose")
        require((camera.get("width"), camera.get("height")) == size and
                type(camera.get("fov_deg")) in (float, int) and
                1 <= camera["fov_deg"] <= 170, "pinned four-view profile required")
    return packet


def transform(carla, values):
    x, y, z, pitch, yaw, roll = vector(values, 6, "Native pose")
    return carla.Transform(carla.Location(x=x, y=y, z=z),
                           carla.Rotation(pitch=pitch, yaw=yaw, roll=roll))


class BridgeScene:
    """Owns all new actors/sensors; the operator provides an exclusive client."""

    def __init__(self, client, packet, case_id, source_root, *, carla_module=None,
                 snapshot_fn=None, restore_fn=None, bind_fn=None):
        self.client = client
        self.packet = validate(packet, case_id)
        self.case_id = case_id
        self.carla = carla_module
        self.source_root = source_root
        self.bind_fn = bind_fn
        self.snapshot_fn = snapshot_fn
        self.restore_fn = restore_fn
        self.saved = None
        self.world = None
        self.actors = {}
        self.sensors = {}
        self.closed = False
        self.release = None
        self.route_indices = {role: 0 for role in self.packet["actors"]}
        self.last_world_frame = None

    def begin(self):
        if self.bind_fn is None:
            from source_bind import bind
            self.bind_fn = bind
        self.bound_sources = self.bind_fn(self.packet, self.source_root)
        if self.carla is None:
            import carla
            self.carla = carla
        if self.snapshot_fn is None or self.restore_fn is None:
            from worker_exchange.world_restore import snapshot, restore
            self.snapshot_fn, self.restore_fn = snapshot, restore
        self.saved = self.snapshot_fn(self.client)
        try:
            self.world = self.client.get_world()
            actual = hashlib.sha256(self.world.get_map().to_opendrive().encode()).hexdigest()
            require(actual == self.packet["map_opendrive_sha256"],
                    "live OpenDRIVE differs from reviewed original source")
            settings = self.world.get_settings()
            settings.synchronous_mode = True
            settings.fixed_delta_seconds = .05
            self.world.apply_settings(settings)
            library = self.world.get_blueprint_library()
            for role, item in self.packet["actors"].items():
                actor = self.world.try_spawn_actor(library.find(item["blueprint"]),
                                                   transform(self.carla, item["pose"]))
                require(actor is not None, "reviewed vehicle spawn failed: " + role)
                self.actors[role] = actor
            if self.case_id.split("__")[-1] != "clear_within_100ft":
                blocker = self.packet["opaque_blocker"]
                actor = self.world.try_spawn_actor(library.find(blocker["blueprint"]),
                                                   transform(self.carla, blocker["pose"]))
                require(actor is not None, "opaque blocker spawn failed")
                self.actors["opaque_blocker"] = actor
            for name in CAMERAS:
                item = self.packet["cameras"][name]
                blueprint = library.find("sensor.camera.rgb")
                for key, value in (("image_size_x", item["width"]),
                                   ("image_size_y", item["height"]),
                                   ("fov", item["fov_deg"]), ("sensor_tick", .05)):
                    blueprint.set_attribute(key, str(value))
                sensor = self.world.spawn_actor(blueprint, transform(self.carla, item["pose"]))
                require(sensor is not None, "reviewed camera spawn failed: " + name)
                self.sensors[name] = sensor
            return {"case_id": self.case_id, "map_opendrive_sha256": actual,
                    "actor_roles": sorted(self.actors), "cameras": list(CAMERAS),
                    "physical_completion_claimed": False}
        except BaseException:
            self.close()
            raise

    def _apply_route(self, role, episode_frame):
        actor = self.actors[role]
        spec = self.packet["actors"][role]
        route = spec["route"]
        location = actor.get_location()
        index = self.route_indices[role]
        while index < len(route) - 1 and math.hypot(route[index][0]-location.x,
                                                     route[index][1]-location.y) < 2:
            index += 1
        self.route_indices[role] = index
        target = route[index]
        distance = math.hypot(target[0]-location.x, target[1]-location.y)
        if index == len(route)-1 and distance < 2:
            control = self.carla.VehicleControl(throttle=0, brake=1, steer=0)
            actor.apply_control(control)
            return {"role": role, "route_index": index, "target_speed_mps": 0,
                    "controller_stopped": True}
        transform = actor.get_transform()
        yaw = math.radians(transform.rotation.yaw)
        heading = math.atan2(target[1]-location.y, target[0]-location.x)
        error = math.atan2(math.sin(heading-yaw), math.cos(heading-yaw))
        velocity = actor.get_velocity()
        speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
        requested = spec["target_speed_mps"]
        response = spec.get("response_policy")
        if response and episode_frame >= response["start_frame"]:
            requested = response["target_speed_mps"]
        throttle = max(0.0, min(0.65, 0.20*(requested-speed)))
        brake = max(0.0, min(0.7, 0.25*(speed-requested)))
        steer = max(-0.65, min(0.65, 1.0*error))
        actor.apply_control(self.carla.VehicleControl(throttle=throttle, brake=brake,
                                                       steer=steer))
        return {"role": role, "route_index": index, "target_speed_mps": requested,
                "observed_speed_mps": speed, "requested_steer": steer,
                "controller_stopped": False}

    def tick(self, episode_frame):
        require(self.world is not None and not self.closed, "Native scene not active")
        commands = [self._apply_route(role, episode_frame) for role in self.packet["actors"]]
        world_frame = self.world.tick()
        require(type(world_frame) is int and
                (self.last_world_frame is None or world_frame == self.last_world_frame+1),
                "original CARLA world frame discontinuity")
        self.last_world_frame = world_frame
        return {"world_frame": world_frame, "commands": commands}

    def close(self):
        if self.closed:
            return self.release
        errors = []
        for sensor in reversed(list(self.sensors.values())):
            for operation in (sensor.stop, sensor.destroy):
                try:
                    operation()
                except Exception as exc:
                    errors.append(str(exc))
        for actor in reversed(list(self.actors.values())):
            try:
                actor.destroy()
            except Exception as exc:
                errors.append(str(exc))
        restored = None
        if self.saved is not None:
            try:
                restored = self.restore_fn(self.client, self.saved)
            except Exception as exc:
                errors.append(str(exc))
        self.release = {"actors_released": not errors, "sensors_released": not errors,
                        "world_restored": bool(restored and restored.get("restored")),
                        "restoration": restored, "errors": errors}
        self.closed = True
        require((self.release["world_restored"] or self.saved is None) and not errors,
                "release or restoration readback failed: " + "; ".join(errors))
        return self.release
